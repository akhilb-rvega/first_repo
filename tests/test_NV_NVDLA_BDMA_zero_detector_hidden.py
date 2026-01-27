# -*- coding: utf-8 -*-

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, with_timeout
from cocotb.result import SimTimeoutError
from cocotb_tools.runner import get_runner

CLK_PERIOD_NS = 10
MAX_WAIT_CYCLES = 1000
DEFAULT_TEST_TIMEOUT_CYCLES = 10000


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
async def run_with_test_timeout(coro, name, timeout_cycles=DEFAULT_TEST_TIMEOUT_CYCLES):
    try:
        await with_timeout(coro, timeout_cycles * CLK_PERIOD_NS, "ns")
    except Exception as e:
        raise SimTimeoutError(f"Timeout in test '{name}'") from e


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await Timer(50, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def setup_dut(dut, block_cfg=0):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = block_cfg
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1


async def send_beat(dut, val):
    dut.nvdla_bdma_inp_data_pd.value = val
    dut.nvdla_bdma_inp_data_pvld.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            dut.nvdla_bdma_inp_data_pvld.value = 0
            return


async def accept_data(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            v = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return v


async def accept_zero_flag(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            v = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return v


# -------------------------------------------------------------
# New Multi-Beat Tests
# -------------------------------------------------------------

@cocotb.test()
async def test_block_16_all_zero(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)  # 16 beats
        for _ in range(16):
            await send_beat(dut, 0)
            await accept_data(dut)
        assert await accept_zero_flag(dut) == 1

    await run_with_test_timeout(body(), "test_block_16_all_zero")


@cocotb.test()
async def test_block_16_one_nonzero(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)
        for i in range(16):
            val = 0 if i != 7 else 0xDE
            await send_beat(dut, val)
            await accept_data(dut)
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_block_16_one_nonzero")


@cocotb.test()
async def test_block_32_random(dut):
    async def body():
        await setup_dut(dut, block_cfg=1)  # 32 beats
        any_nz = False
        for _ in range(32):
            val = random.randint(0, 255)
            if val != 0:
                any_nz = True
            await send_beat(dut, val)
            await accept_data(dut)
        flag = await accept_zero_flag(dut)
        assert flag == (0 if any_nz else 1)

    await run_with_test_timeout(body(), "test_block_32_random")


@cocotb.test()
async def test_block_backpressure_mid_block(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)
        for i in range(16):
            await send_beat(dut, 0)
            if i % 4 == 0:
                await Timer(30, units="ns")  # stall
            await accept_data(dut)
        assert await accept_zero_flag(dut) == 1

    await run_with_test_timeout(body(), "test_block_backpressure_mid_block")


@cocotb.test()
async def test_block_boundary_separation(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)

        # Block 1: zero
        for _ in range(16):
            await send_beat(dut, 0)
            await accept_data(dut)
        assert await accept_zero_flag(dut) == 1

        # Block 2: non-zero
        for i in range(16):
            await send_beat(dut, 0x1 if i == 0 else 0)
            await accept_data(dut)
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_block_boundary_separation")


@cocotb.test()
async def test_disable_mid_block(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)

        for _ in range(5):
            await send_beat(dut, 0)
            await accept_data(dut)

        dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
        await RisingEdge(dut.nvdla_core_clk)

        # No flag should appear
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    await run_with_test_timeout(body(), "test_disable_mid_block")


@cocotb.test()
async def test_multiple_blocks(dut):
    async def body():
        await setup_dut(dut, block_cfg=0)

        for _ in range(3):
            for _ in range(16):
                await send_beat(dut, 0)
                await accept_data(dut)
            assert await accept_zero_flag(dut) == 1

    await run_with_test_timeout(body(), "test_multiple_blocks")
