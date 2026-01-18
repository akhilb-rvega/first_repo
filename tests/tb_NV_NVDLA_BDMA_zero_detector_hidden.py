# test_zero_detector.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import pytest
from cocotb_test.simulator import run

CLK_PERIOD_NS = 10


async def reset_dut(dut):
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    await Timer(50, unit="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)


async def send_beat(dut, value):
    """Send one input beat and wait for acceptance"""
    dut.nvdla_bdma_inp_data_pd.value = value
    dut.nvdla_bdma_inp_data_pvld.value = 1

    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break

    dut.nvdla_bdma_inp_data_pvld.value = 0


async def recv_data(dut):
    """Receive one output data beat"""
    dut.nvdla_bdma_out_data_prdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            data = int(dut.nvdla_bdma_out_data_pd.value)
            dut.nvdla_bdma_out_data_prdy.value = 0
            return data


@cocotb.test()
async def test_bypass_mode(dut):
    """Bypass mode: data passes through, no metadata"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0

    test_vectors = [0x00, 0x12, 0xFF, 0x01]

    for val in test_vectors:
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Bypass data mismatch: {out} != {val}"

        # Metadata must never assert in bypass
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    cocotb.log.info("Bypass mode test PASSED")


def test_tb_NV_NVDLA_BDMA_zero_detector_runner():
    """Test runner for cocotb-test"""
    run(
        verilog_sources=["sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v"],
        toplevel="NV_NVDLA_BDMA_zero_detector",
        module="tb_NV_NVDLA_BDMA_zero_detector_hidden",
        simulator="icarus",
        compile_args=["-g2012", "-I", "sources"],
    )
