# -*- coding: utf-8 -*-

import os
import sys
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_tools.runner import get_runner

# =============================================================================
# Constants
# =============================================================================
CLK_PERIOD_NS = 10
TIMEOUT_NS = 20_000


# =============================================================================
# Helper functions
# =============================================================================

async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0

    dut.nvdla_bdma_inp_data_pd.value = 0
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

    for _ in range(TIMEOUT_NS // CLK_PERIOD_NS):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break
    else:
        assert False, "Timeout waiting for inp_data_prdy"

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def recv_data(dut):
    for _ in range(TIMEOUT_NS // CLK_PERIOD_NS):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            return dut.nvdla_bdma_out_data_pd.value.integer

    assert False, "Timeout waiting for out_data_pvld"


async def recv_block_result(dut):
    for _ in range(TIMEOUT_NS // CLK_PERIOD_NS):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            return int(dut.nvdla_bdma_out_blk_is_zero.value)

    assert False, "Timeout waiting for blk_is_zero_vld"


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
        out = await recv_data(dut)

        assert out == data, (
            f"Output mismatch at beat {i}: expected {hex(data)}, got {hex(out)}"
        )

    res = await recv_block_result(dut)
    expected = 0 if seen_nonzero else 1

    assert res == expected, (
        f"Block zero mismatch: expected {expected}, got {res}"
    )


# =============================================================================
# Tests
# =============================================================================

@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_reset_test(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    assert dut.nvdla_bdma_out_data_pvld.value == 0
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test(timeout_time=10, timeout_unit="us")
async def cocotb_block16_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=0, force_nonzero=False)


@cocotb.test(timeout_time=10, timeout_unit="us")
async def cocotb_block16_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=0, force_nonzero=True)


@cocotb.test(timeout_time=15, timeout_unit="us")
async def cocotb_block32_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=1, force_nonzero=False)


@cocotb.test(timeout_time=15, timeout_unit="us")
async def cocotb_block32_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=1, force_nonzero=True)


@cocotb.test(timeout_time=25, timeout_unit="us")
async def cocotb_block64_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=2, force_nonzero=False)


@cocotb.test(timeout_time=40, timeout_unit="us")
async def cocotb_block128_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)
    await run_block_test(dut, cfg=3, force_nonzero=False)


# =============================================================================
# Advanced / Stress Tests
# =============================================================================

@cocotb.test(timeout_time=20, timeout_unit="us")
async def cocotb_disable_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    for _ in range(4):
        await send_beat(dut, random.getrandbits(512))
        await recv_data(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)

    for _ in range(50):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test(timeout_time=20, timeout_unit="us")
async def cocotb_output_backpressure(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    await send_beat(dut, 0)
    await Timer(100, units="ns")

    assert dut.nvdla_bdma_out_data_pvld.value == 1

    dut.nvdla_bdma_out_data_prdy.value = 1
    out = await recv_data(dut)

    assert out == 0


@cocotb.test(timeout_time=50, timeout_unit="us")
async def cocotb_randomized_fuzz(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(10):
        cfg = random.randint(0, 3)
        force_nonzero = random.choice([True, False])
        await run_block_test(dut, cfg, force_nonzero)


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
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "icarus")

    proj_dir = Path(__file__).resolve().parent.parent
    rtl_dir = proj_dir / "sources" / "vmod" / "nvdla" / "bdma"

    # ------------------------------------------------------------------
    # Compile ONLY the top module RTL
    # ------------------------------------------------------------------
    rtl_sources = [
        str(rtl_dir / "NV_NVDLA_BDMA_zero_detector.v")
    ]

    # ------------------------------------------------------------------
    # Runner flow
    # ------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# Pytest-compatible runner
# ---------------------------------------------------------------------
def test_NV_NVDLA_BDMA_zero_detector_hidden():
    """Pytest-compatible cocotb test runner using cocotb_tools.runner"""
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "icarus")

    proj_dir = Path(__file__).resolve().parent.parent
    rtl_dir = proj_dir / "sources" / "vmod" / "nvdla" / "bdma"

    # ------------------------------------------------------------------
    # Compile ONLY the top module RTL
    # ------------------------------------------------------------------
    rtl_sources = [
        str(rtl_dir / "NV_NVDLA_BDMA_zero_detector.v")
    ]

    # ------------------------------------------------------------------
    # Runner flow
    # ------------------------------------------------------------------
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
