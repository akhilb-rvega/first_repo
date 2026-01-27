# -*- coding: utf-8 -*-

import os
import sys
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotb_test.simulator import run
from cocotb_tools.runner import get_runner

# =============================================================================
# Constants
# =============================================================================
CLK_PERIOD_NS = 10
TIMEOUT_NS = 10_000


# =============================================================================
# Helper functions (cocotb only)
# =============================================================================
async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 1
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
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


def beats_from_cfg(cfg):
    return [16, 32, 64, 128][cfg]


async def run_block_test(dut, cfg, force_nonzero=False):
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    beats = beats_from_cfg(cfg)
    seen_nonzero = False

    for i in range(beats):
        if force_nonzero and i == beats // 2:
            data = 1
            seen_nonzero = True
        else:
            data = random.getrandbits(512)
            if data != 0:
                seen_nonzero = True

        await send_beat(dut, data)
        out = await with_timeout(recv_data(dut), TIMEOUT_NS, "ns")

        if out != data:
            raise TestFailure("Output data mismatch")

    res = await with_timeout(recv_block_result(dut), TIMEOUT_NS, "ns")
    expected = 0 if seen_nonzero else 1

    if res != expected:
        raise TestFailure(f"Block zero error: expected {expected}, got {res}")


# =============================================================================
# Cocotb tests (NOT collected by pytest)
# =============================================================================
@cocotb.test()
async def cocotb_reset_test(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    assert dut.nvdla_bdma_out_data_pvld.value == 0
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test()
async def cocotb_block16_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=0, force_nonzero=False)


@cocotb.test()
async def cocotb_block16_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=0, force_nonzero=True)


@cocotb.test()
async def cocotb_block32_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=1, force_nonzero=False)


@cocotb.test()
async def cocotb_block32_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=1, force_nonzero=True)


@cocotb.test()
async def cocotb_block64_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=2, force_nonzero=False)


@cocotb.test()
async def cocotb_block64_single_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=2, force_nonzero=True)


@cocotb.test()
async def cocotb_block128_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=3, force_nonzero=False)


@cocotb.test()
async def cocotb_disable_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    for _ in range(5):
        await send_beat(dut, random.getrandbits(512))
        await recv_data(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)

    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test()
async def cocotb_output_backpressure(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, units="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    await send_beat(dut, 0)
    await Timer(50, units="ns")

    assert dut.nvdla_bdma_out_data_pvld.value == 1

    dut.nvdla_bdma_out_data_prdy.value = 1
    await recv_data(dut)



# =============================================================================
# Pytest entry point (ONLY thing pytest collects)
# =============================================================================
def test_NV_NVDLA_BDMA_zero_detector_hidden():
    proj_dir = Path(__file__).resolve().parent.parent

    run(
        verilog_sources=[
            str(proj_dir / "rtl" / "NV_NVDLA_BDMA_zero_detector.v")
        ],
        toplevel="NV_NVDLA_BDMA_zero_detector",
        module="test_NV_NVDLA_BDMA_zero_detector_hidden",
        simulator="iverilog",
        waves=False,
    )


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
