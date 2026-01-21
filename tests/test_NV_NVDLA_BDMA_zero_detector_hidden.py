# -*- coding: utf-8 -*-
# test_zero_detector.py

import sys
import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, with_timeout
from cocotb.result import SimTimeoutError
from cocotb_tools.runner import get_runner


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------
os.environ["PYTHONIOENCODING"] = "utf-8"

CLK_PERIOD_NS = 10
MAX_WAIT_CYCLES = 1000
DEFAULT_TEST_TIMEOUT_CYCLES = 5000


# ---------------------------------------------------------------------
# Timeout wrapper (PER TEST)
# ---------------------------------------------------------------------
async def run_with_test_timeout(coro, test_name, timeout_cycles=DEFAULT_TEST_TIMEOUT_CYCLES):
    try:
        await with_timeout(
            coro,
            timeout_cycles * CLK_PERIOD_NS,
            "ns",
        )
    except Exception as e:
        raise SimTimeoutError(
            f"Timeout in test '{test_name}' after {timeout_cycles} cycles"
        ) from e


# ---------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------
async def _rising_edge_with_timeout(clk, timeout_cycles, err):
    try:
        await with_timeout(
            RisingEdge(clk),
            timeout_cycles * CLK_PERIOD_NS,
            "ns",
        )
    except Exception as e:
        raise SimTimeoutError(err) from e


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await Timer(50, units="ns")
    dut.nvdla_core_rstn.value = 1
    await _rising_edge_with_timeout(dut.nvdla_core_clk, MAX_WAIT_CYCLES, "Reset timeout")


async def setup_dut(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1


async def send_input(dut, data):
    dut.nvdla_bdma_inp_data_pd.value = data
    dut.nvdla_bdma_inp_data_pvld.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            dut.nvdla_bdma_inp_data_pvld.value = 0
            return


async def accept_output(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            val = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return val


async def accept_zero_flag(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            val = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return val



@cocotb.test()
async def test_single_zero(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0x00)
        assert await accept_output(dut) == 0x00
        assert await accept_zero_flag(dut) == 1

    await run_with_test_timeout(body(), "test_single_zero")


@cocotb.test()
async def test_single_non_zero(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0xAB)
        assert await accept_output(dut) == 0xAB
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_single_non_zero")


@cocotb.test()
async def test_disabled_mode(dut):
    async def body():
        await setup_dut(dut)
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
        await send_input(dut, 0x00)
        await accept_output(dut)
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    await run_with_test_timeout(body(), "test_disabled_mode")


@cocotb.test()
async def test_re_enable(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0x55)
        await accept_output(dut)
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_re_enable")


@cocotb.test()
async def test_output_backpressure(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0x00)
        await Timer(50, units="ns")
        assert await accept_output(dut) == 0x00
        assert await accept_zero_flag(dut) == 1

    await run_with_test_timeout(body(), "test_output_backpressure")


@cocotb.test()
async def test_zero_flag_backpressure(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0x22)
        await accept_output(dut)
        await Timer(50, units="ns")
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_zero_flag_backpressure")


@cocotb.test()
async def test_max_value(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0xFF)
        assert await accept_output(dut) == 0xFF
        assert await accept_zero_flag(dut) == 0

    await run_with_test_timeout(body(), "test_max_value")


@cocotb.test()
async def test_random_values(dut):
    async def body():
        await setup_dut(dut)
        for _ in range(5):
            val = random.randint(0, 255)
            await send_input(dut, val)
            assert await accept_output(dut) == val
            assert await accept_zero_flag(dut) == (1 if val == 0 else 0)

    await run_with_test_timeout(body(), "test_random_values", timeout_cycles=8000)


@cocotb.test()
async def test_reset_during_operation(dut):
    async def body():
        await setup_dut(dut)
        await send_input(dut, 0x00)
        dut.nvdla_core_rstn.value = 0
        await Timer(20, units="ns")
        dut.nvdla_core_rstn.value = 1
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 0
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    await run_with_test_timeout(body(), "test_reset_during_operation")


# ---------------------------------------------------------------------
# Pytest-compatible runner
# ---------------------------------------------------------------------
def test_NV_NVDLA_BDMA_zero_detector_hidden():
    """Pytest-compatible cocotb test runner using cocotb_tools.runner"""
    sim = os.getenv("SIM", "icarus")
    proj_dir = Path(__file__).resolve().parent.parent
    rtl_dir = proj_dir / "sources" / "vmod" / "nvdla" / "bdma"
    vlibs_dir = proj_dir / "sources" / "vmod" / "vlibs"
    rams_model_dir = proj_dir / "sources" / "vmod" / "rams" / "model"
    rams_synth_dir = proj_dir / "sources" / "vmod" / "rams" / "synth"
    include_dir = proj_dir / "sources" / "vmod" / "include"
    # ------------------------------------------------------------------
    # Collect sources
    # ------------------------------------------------------------------
    # Exclude duplicate SSYNC modules
    vlibs_sources = sorted([
        str(f) for f in vlibs_dir.glob("*.v")
        if f.name not in ["p_SSYNC3DO.v", "p_SSYNC3DO_S_PPP.v"]
    ])
    rams_model_sources = sorted(str(f) for f in rams_model_dir.glob("*.v"))
    rams_synth_sources = sorted(str(f) for f in rams_synth_dir.glob("*.v"))
    # Exclude patterns for RTL sources
    EXCLUDE_PATTERNS = ["sram_stub", "simple_tb_assembly_buffer", "nv_ram_sim_models", "ram_stubs"]
    rtl_sources = sorted(
        str(f) for f in rtl_dir.glob("*.v")
        if not any(p in f.name for p in EXCLUDE_PATTERNS)
    )
    verilog_sources = (
        vlibs_sources +
        rams_model_sources +
        rams_synth_sources +
        rtl_sources
    )
    # ------------------------------------------------------------------
    # Runner flow
    # ------------------------------------------------------------------
    runner = get_runner(sim)
    runner.build(
        sources=verilog_sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        includes=[str(include_dir), str(vlibs_dir)],
        defines={
            "SYNTHESIS": 1, # Skip unsupported SV constructs in Icarus
        },
        build_args=["-g2012"],
        always=True,
    )
    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="test_NV_NVDLA_BDMA_zero_detector_hidden",
    )
