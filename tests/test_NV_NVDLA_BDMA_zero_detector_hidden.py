# -*- coding: utf-8 -*-

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_tools.runner import get_runner

CLK_PERIOD_NS = 10


# ================================================================
# Helpers
# ================================================================

async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 1
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    await Timer(50, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def send_beat(dut, data):
    dut.nvdla_bdma_inp_data_pd.value = data
    dut.nvdla_bdma_inp_data_pvld.value = 1

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def recv_data(dut):
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            return dut.nvdla_bdma_out_data_pd.value.integer


async def recv_block_result(dut):
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            return int(dut.nvdla_bdma_out_blk_is_zero.value)


def beats(cfg):
    return [16, 32, 64, 128][cfg]


# ================================================================
# TEST 1 — Reset Sanity
# ================================================================

@cocotb.test()
async def test_reset(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)


# ================================================================
# TEST 2 — Last Beat Timing
# ================================================================

@cocotb.test()
async def test_block_result_timing(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    for _ in range(15):
        await send_beat(dut, 0)
        await recv_data(dut)

    dut.nvdla_bdma_inp_data_pd.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 1

    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1


# ================================================================
# TEST 3 — All Zero Blocks
# ================================================================

@cocotb.test()
async def test_all_zero_blocks(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for cfg in range(4):
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        for _ in range(beats(cfg)):
            await send_beat(dut, 0)
            await recv_data(dut)

        res = await recv_block_result(dut)
        assert res == 1


# ================================================================
# TEST 4 — Single Nonzero
# ================================================================

@cocotb.test()
async def test_single_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for cfg in range(4):
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        for i in range(beats(cfg)):
            data = 1 if i == beats(cfg) // 2 else 0
            await send_beat(dut, data)
            await recv_data(dut)

        res = await recv_block_result(dut)
        assert res == 0


# ================================================================
# TEST 5 — Random Data Blocks
# ================================================================

@cocotb.test()
async def test_random_blocks(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(20):
        cfg = random.randint(0, 3)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        seen_nonzero = False

        for _ in range(beats(cfg)):
            data = random.getrandbits(len(dut.nvdla_bdma_inp_data_pd))
            if data != 0:
                seen_nonzero = True

            await send_beat(dut, data)
            await recv_data(dut)

        res = await recv_block_result(dut)
        assert res == (0 if seen_nonzero else 1)


# ================================================================
# TEST 6 — Backpressure Random
# ================================================================

@cocotb.test()
async def test_random_backpressure(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(20):
        cfg = random.randint(0, 3)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        for _ in range(beats(cfg)):
            if random.random() < 0.3:
                dut.nvdla_bdma_out_data_prdy.value = 0
                for _ in range(random.randint(1, 5)):
                    await RisingEdge(dut.nvdla_core_clk)
                dut.nvdla_bdma_out_data_prdy.value = 1

            await send_beat(dut, random.getrandbits(len(dut.nvdla_bdma_inp_data_pd)))
            await recv_data(dut)

        await recv_block_result(dut)


# ================================================================
# TEST 7 — Idle Insertion
# ================================================================

@cocotb.test()
async def test_idle_cycles(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 1

    for _ in range(beats(1)):
        if random.random() < 0.4:
            for _ in range(random.randint(1, 5)):
                await RisingEdge(dut.nvdla_core_clk)

        await send_beat(dut, random.getrandbits(len(dut.nvdla_bdma_inp_data_pd)))
        await recv_data(dut)

    await recv_block_result(dut)


# ================================================================
# TEST 8 — Disable Mid Block
# ================================================================

@cocotb.test()
async def test_disable_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    for _ in range(6):
        await send_beat(dut, random.getrandbits(len(dut.nvdla_bdma_inp_data_pd)))
        await recv_data(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0

    for _ in range(30):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


# ================================================================
# TEST 9 — Reset Mid Block
# ================================================================

@cocotb.test()
async def test_reset_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 2

    for _ in range(20):
        await send_beat(dut, random.getrandbits(len(dut.nvdla_bdma_inp_data_pd)))

    dut.nvdla_core_rstn.value = 0
    await Timer(40, units="ns")
    dut.nvdla_core_rstn.value = 1

    for _ in range(20):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


# ================================================================
# TEST 10 — Extreme Backpressure on Last Beat
# ================================================================

@cocotb.test()
async def test_extreme_backpressure_last_beat(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    cfg = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

    for _ in range(beats(cfg) - 1):
        await send_beat(dut, 0)
        await recv_data(dut)

    dut.nvdla_bdma_out_data_prdy.value = 0
    await send_beat(dut, 0)

    for _ in range(30):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    dut.nvdla_bdma_out_data_prdy.value = 1
    await recv_data(dut)
    await recv_block_result(dut)


# ================================================================
# TEST 11 — Continuous Blocks
# ================================================================

@cocotb.test()
async def test_continuous_blocks(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(10):
        cfg = random.randint(0, 3)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        for _ in range(beats(cfg)):
            await send_beat(dut, random.getrandbits(len(dut.nvdla_bdma_inp_data_pd)))
            await recv_data(dut)

        await recv_block_result(dut)


# ================================================================
# TEST 12 — Long Random Stress
# ================================================================

@cocotb.test(timeout_time=200, timeout_unit="us")
async def test_long_random_stress(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(200):
        cfg = random.randint(0, 3)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg

        seen_nonzero = False

        for _ in range(beats(cfg)):
            data = random.getrandbits(len(dut.nvdla_bdma_inp_data_pd))
            if data != 0:
                seen_nonzero = True

            if random.random() < 0.3:
                dut.nvdla_bdma_out_data_prdy.value = 0
                for _ in range(random.randint(1, 4)):
                    await RisingEdge(dut.nvdla_core_clk)
                dut.nvdla_bdma_out_data_prdy.value = 1

            await send_beat(dut, data)
            await recv_data(dut)

        res = await recv_block_result(dut)
        assert res == (0 if seen_nonzero else 1)


# =============================================================================
# Pytest-compatible runner
# =============================================================================

def test_NV_NVDLA_BDMA_zero_detector_hidden():
    sim = os.getenv("SIM", "icarus")

    proj_dir = Path(__file__).resolve().parent.parent
    rtl_dir = proj_dir / "sources" / "vmod" / "nvdla" / "bdma"

    rtl_sources = [
        str(rtl_dir / "NV_NVDLA_BDMA_zero_detector.v")
    ]

    runner = get_runner(sim)

    runner.build(
        sources=rtl_sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        build_args=["-g2012"],
        always=True,
    )

    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="test_NV_NVDLA_BDMA_zero_detector_hidden",
    )
