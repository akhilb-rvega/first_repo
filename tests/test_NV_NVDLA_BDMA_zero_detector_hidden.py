# -*- coding: utf-8 -*-

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_tools.runner import get_runner

CLK_PERIOD_NS = 10




DATA_WIDTH  = 512
BLOCK_BEATS = 16

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def rand_data(width=DATA_WIDTH):
    return random.getrandbits(width)

async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    await Timer(100, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)

async def send_beat(dut, data):
    dut.nvdla_bdma_inp_data_pd.value   = data
    dut.nvdla_bdma_inp_data_pvld.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break
    dut.nvdla_bdma_inp_data_pvld.value = 0

async def recv_beat(dut):
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            return int(dut.nvdla_bdma_out_data_pd.value)

async def recv_block_result(dut):
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            return int(dut.nvdla_bdma_out_blk_is_zero.value)

async def send_block(dut, data_list):
    for d in data_list:
        await send_beat(dut, d)

async def recv_block(dut, beats=BLOCK_BEATS):
    out = []
    for _ in range(beats):
        out.append(await recv_beat(dut))
    blk_zero = await recv_block_result(dut)
    return out, blk_zero

# -----------------------------------------------------------------------------
# Reference Model
# -----------------------------------------------------------------------------

def ref_block_zero(data_list):
    return int(all(x == 0 for x in data_list))

async def common_test_setup(dut):
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())

    dut.nvdla_bdma_inp_data_pvld.value       = 0
    dut.nvdla_bdma_out_data_prdy.value       = 1
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value     = 1

    await reset_dut(dut)

async def run_test_case(dut, data_list, test_name=""):
    await send_block(dut, data_list)
    out, blk_zero = await recv_block(dut)

    if out != data_list:
        raise TestFailure(f"{test_name}: Data mismatch")

    exp_zero = ref_block_zero(data_list)
    if blk_zero != exp_zero:
        raise TestFailure(f"{test_name}: blk_zero mismatch exp={exp_zero} got={blk_zero}")

# -----------------------------------------------------------------------------
# Individual Cocotb Tests (10+)
# -----------------------------------------------------------------------------

@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc1_all_zeros(dut):
    await common_test_setup(dut)
    data = [0] * BLOCK_BEATS
    await run_test_case(dut, data, "TC1_All_Zeros")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc2_nonzero_first(dut):
    await common_test_setup(dut)
    data = [rand_data()] + [0] * (BLOCK_BEATS - 1)
    await run_test_case(dut, data, "TC2_NonZero_First")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc3_nonzero_last(dut):
    await common_test_setup(dut)
    data = [0] * (BLOCK_BEATS - 1) + [rand_data()]
    await run_test_case(dut, data, "TC3_NonZero_Last")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc4_random(dut):
    await common_test_setup(dut)
    data = [rand_data() for _ in range(BLOCK_BEATS)]
    await run_test_case(dut, data, "TC4_Random")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc5_alternating(dut):
    await common_test_setup(dut)
    data = [(0 if i % 2 == 0 else rand_data()) for i in range(BLOCK_BEATS)]
    await run_test_case(dut, data, "TC5_Alternating")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc6_single_bit(dut):
    await common_test_setup(dut)
    data = [1 << random.randint(0, DATA_WIDTH - 1)] + [0] * (BLOCK_BEATS - 1)
    await run_test_case(dut, data, "TC6_SingleBit")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc7_all_ones(dut):
    await common_test_setup(dut)
    data = [(1 << DATA_WIDTH) - 1] * BLOCK_BEATS
    await run_test_case(dut, data, "TC7_All_Ones")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc8_sparse(dut):
    await common_test_setup(dut)
    data = [0] * BLOCK_BEATS
    idx = random.randint(0, BLOCK_BEATS - 1)
    data[idx] = rand_data()
    await run_test_case(dut, data, "TC8_Sparse")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc9_two_blocks(dut):
    await common_test_setup(dut)
    for i in range(2):
        data = [rand_data() for _ in range(BLOCK_BEATS)]
        await run_test_case(dut, data, f"TC9_Block_{i}")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc10_stress(dut):
    await common_test_setup(dut)
    for i in range(5):
        if i % 2 == 0:
            data = [0] * BLOCK_BEATS
        else:
            data = [rand_data() for _ in range(BLOCK_BEATS)]
        await run_test_case(dut, data, f"TC10_Stress_{i}")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc11_walking_one(dut):
    await common_test_setup(dut)
    for bit in [0, DATA_WIDTH // 2, DATA_WIDTH - 1]:
        data = [1 << bit] + [0] * (BLOCK_BEATS - 1)
        await run_test_case(dut, data, f"TC11_WalkingOne_{bit}")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def tc12_walking_zero(dut):
    await common_test_setup(dut)
    for bit in [0, DATA_WIDTH // 2, DATA_WIDTH - 1]:
        data = [(1 << DATA_WIDTH) - 1] * BLOCK_BEATS
        data[0] ^= (1 << bit)
        await run_test_case(dut, data, f"TC12_WalkingZero_{bit}")



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
