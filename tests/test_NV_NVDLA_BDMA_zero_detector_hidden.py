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

# =============================================================================
# Helpers
# =============================================================================

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


# =============================================================================
# NEW TEST – Golden RTL timing discriminator
# =============================================================================

@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_test_block_result_timing(dut):
    """
    Ensures block result valid asserts IMMEDIATELY when the last beat
    is accepted. Golden RTL passes. FSM RTL fails.
    """
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0  # 16 beats
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    for _ in range(15):
        await send_beat(dut, 0)
        await recv_data(dut)

    # Last beat
    dut.nvdla_bdma_inp_data_pd.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 1

    await RisingEdge(dut.nvdla_core_clk)

    if not dut.nvdla_bdma_inp_data_prdy.value:
        raise AssertionError("Last beat not accepted")

    # Golden RTL: result valid must assert immediately
    if dut.nvdla_bdma_out_blk_is_zero_vld.value != 1:
        raise AssertionError(
            "Block result valid not asserted immediately on last beat.\n"
            "Golden RTL: PASS\n"
            "FSM RTL: FAIL"
        )

    if dut.nvdla_bdma_out_blk_is_zero.value != 1:
        raise AssertionError("Block result incorrect")

    dut.nvdla_bdma_inp_data_pvld.value = 0


# =============================================================================
# Core block runner + scoreboard
# =============================================================================

async def run_block_with_checks(
    dut,
    cfg,
    pattern="random",
    backpressure=False,
    idle_insert=False,
):
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = cfg
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    beat_count = beats(cfg)
    seen_nonzero = False
    out_beats_seen = 0

    for i in range(beat_count):

        if pattern == "zero":
            data = 0
        elif pattern == "nonzero":
            data = 1 if i == beat_count // 2 else 0
            if data != 0:
                seen_nonzero = True
        else:
            data = random.getrandbits(512)
            if data != 0:
                seen_nonzero = True

        if backpressure and random.random() < 0.3:
            dut.nvdla_bdma_out_data_prdy.value = 0
            for _ in range(random.randint(1, 4)):
                await RisingEdge(dut.nvdla_core_clk)
            dut.nvdla_bdma_out_data_prdy.value = 1

        if idle_insert and random.random() < 0.3:
            for _ in range(random.randint(1, 4)):
                await RisingEdge(dut.nvdla_core_clk)

        await send_beat(dut, data)

        while True:
            await RisingEdge(dut.nvdla_core_clk)

            if dut.nvdla_bdma_out_blk_is_zero_vld.value:
                assert out_beats_seen == beat_count - 1, \
                    f"blk_vld early at beat {out_beats_seen}"

            if dut.nvdla_bdma_out_data_pvld.value:
                out = dut.nvdla_bdma_out_data_pd.value.integer
                assert out == data, "Data mismatch"
                out_beats_seen += 1
                break

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            res = int(dut.nvdla_bdma_out_blk_is_zero.value)
            break

    expected = 0 if seen_nonzero else 1
    assert res == expected, \
        f"Block result mismatch: expected={expected} got={res}"


# =============================================================================
# Existing Tests (UNCHANGED)
# =============================================================================

@cocotb.test(timeout_time=0.5, timeout_unit="us")
async def cocotb_test_reset(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)


@cocotb.test(timeout_time=1, timeout_unit="us")
async def cocotb_test_overflow_flag_stays_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(200):
        await RisingEdge(dut.nvdla_core_clk)
        assert int(dut.nvdla_bdma_zd2reg_error_overflow.value) == 0


@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_test_all_block_sizes_zero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for cfg in range(4):
        await run_block_with_checks(dut, cfg, "zero")


@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_test_all_block_sizes_single_nonzero(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for cfg in range(4):
        await run_block_with_checks(dut, cfg, "nonzero")


@cocotb.test(timeout_time=4, timeout_unit="us")
async def cocotb_test_random_with_backpressure_and_idle(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(15):
        cfg = random.randint(0, 3)
        await run_block_with_checks(
            dut, cfg, "random", backpressure=True, idle_insert=True
        )


@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_test_zero_followed_by_nonzero_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    await run_block_with_checks(dut, 0, "zero")
    await run_block_with_checks(dut, 0, "nonzero")


@cocotb.test(timeout_time=2, timeout_unit="us")
async def cocotb_test_nonzero_followed_by_zero_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    await run_block_with_checks(dut, 1, "nonzero")
    await run_block_with_checks(dut, 1, "zero")


@cocotb.test(timeout_time=3, timeout_unit="us")
async def cocotb_test_disable_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    for _ in range(8):
        await send_beat(dut, random.getrandbits(512))
        await recv_data(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0

    for _ in range(30):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0


@cocotb.test(timeout_time=3, timeout_unit="us")
async def cocotb_test_abort_mid_block_data_leak(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    for _ in range(4):
        await send_beat(dut, 0)
        await recv_data(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)

    dut.nvdla_bdma_inp_data_pd.value = (1 << 511)
    dut.nvdla_bdma_inp_data_pvld.value = 1

    for _ in range(10):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_inp_data_prdy.value == 0
        assert dut.nvdla_bdma_out_data_pvld.value == 0
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    dut.nvdla_bdma_inp_data_pvld.value = 0

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await RisingEdge(dut.nvdla_core_clk)

    for _ in range(16):
        await send_beat(dut, 0)
        await recv_data(dut)

    res = await recv_block_result(dut)
    assert res == 1


@cocotb.test(timeout_time=3, timeout_unit="us")
async def cocotb_test_extreme_backpressure_on_last_beat(dut):
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

    for _ in range(40):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    dut.nvdla_bdma_out_data_prdy.value = 1
    await recv_data(dut)
    await recv_block_result(dut)


@cocotb.test(timeout_time=3, timeout_unit="us")
async def cocotb_test_reset_mid_block(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 2

    for _ in range(20):
        await send_beat(dut, random.getrandbits(512))

    dut.nvdla_core_rstn.value = 0
    await Timer(40, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)

    for _ in range(20):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0
        assert dut.nvdla_bdma_out_data_pvld.value == 0


@cocotb.test(timeout_time=200, timeout_unit="us")
async def cocotb_test_long_random_stress(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, "ns").start())
    await reset_dut(dut)

    for _ in range(100):
        cfg = random.randint(0, 3)
        pattern = random.choice(["zero", "nonzero", "random"])
        bp = random.choice([True, False])
        idle = random.choice([True, False])
        await run_block_with_checks(dut, cfg, pattern, bp, idle)


# ---------------------------------------------------------------------
# Pytest-compatible runner
# ---------------------------------------------------------------------

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
