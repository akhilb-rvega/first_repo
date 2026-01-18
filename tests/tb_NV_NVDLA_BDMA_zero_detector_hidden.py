# -*- coding: utf-8 -*-
# test_zero_detector.py
import os
import sys

# Set UTF-8 encoding for Python I/O operations
os.environ["PYTHONIOENCODING"] = "utf-8"

# Reconfigure stdout/stderr to use UTF-8 encoding (especially important on Windows)
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
import pytest
from cocotb_test.simulator import run
import random

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


async def recv_zero_meta(dut):
    """Receive one zero-detection metadata beat"""
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            is_zero = int(dut.nvdla_bdma_out_blk_is_zero.value)
            dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
            return is_zero


async def send_recv_concurrent(dut, value):
    """Send and receive concurrently for direct passthrough scenarios"""
    # Set ready before sending to avoid deadlock in bypass mode
    dut.nvdla_bdma_out_data_prdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Now send data
    dut.nvdla_bdma_inp_data_pd.value = value
    dut.nvdla_bdma_inp_data_pvld.value = 1
    
    # Wait for handshake
    while True:
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value and dut.nvdla_bdma_out_data_pvld.value:
            data = int(dut.nvdla_bdma_out_data_pd.value)
            break
    
    # Clear signals
    dut.nvdla_bdma_inp_data_pvld.value = 0
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
        # Use concurrent send/recv for bypass mode to avoid deadlock
        out = await send_recv_concurrent(dut, val)
        assert out == val, f"Bypass data mismatch: {out} != {val}"

        # Metadata must never assert in bypass
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0

    cocotb.log.info("Bypass mode test PASSED")


@cocotb.test()
async def test_enabled_basic(dut):
    """Enabled mode: check zero detection on each beat"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    test_vectors = [
        (0x00, 1),  # zero -> expect is_zero=1
        (0x12, 0),  # non-zero -> expect is_zero=0
        (0x00, 1),  # zero again
        (0xFF, 0),  # non-zero
    ]

    for val, expected_zero in test_vectors:
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Data mismatch: {out} != {val}"

        meta = await recv_zero_meta(dut)
        assert meta == expected_zero, f"Zero metadata mismatch: {meta} != {expected_zero}"

    cocotb.log.info("Enabled basic test PASSED")


@cocotb.test()
async def test_backpressure(dut):
    """Test backpressure handling on output"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    # Send a beat
    await send_beat(dut, 0xAB)

    # Wait a few cycles before accepting output (backpressure)
    for _ in range(5):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 1, "Output should remain valid"
        assert dut.nvdla_bdma_out_data_pd.value == 0xAB, "Output data should remain stable"

    # Now accept output
    out = await recv_data(dut)
    assert out == 0xAB, f"Data mismatch after backpressure: {out} != 0xAB"

    # Metadata should be available
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"

    cocotb.log.info("Backpressure test PASSED")


@cocotb.test()
async def test_disable_clears_state(dut):
    """Test that disabling clears state"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Start enabled
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1

    # Send a beat and consume both data and metadata
    await send_beat(dut, 0x55)
    out = await recv_data(dut)
    assert out == 0x55
    meta = await recv_zero_meta(dut)
    assert meta == 0, "0x55 should be detected as non-zero"

    # Wait a cycle to ensure metadata handshake completes
    await RisingEdge(dut.nvdla_core_clk)
    
    # Disable mid-operation
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)

    # Metadata should remain clear when disabled
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata should clear when disabled"

    # Switch to bypass mode and verify
    test_val = 0xCC
    out = await send_recv_concurrent(dut, test_val)
    assert out == test_val, f"Bypass after disable failed: {out} != {test_val}"
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata should stay clear in bypass"

    cocotb.log.info("Disable clears state test PASSED")


def test_tb_NV_NVDLA_BDMA_zero_detector_runner():
    """Test runner for cocotb-test"""
    run(
        verilog_sources=["sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v"],
        toplevel="NV_NVDLA_BDMA_zero_detector",
        module="tb_NV_NVDLA_BDMA_zero_detector_hidden",
        simulator="icarus",
        compile_args=["-g2012", "-I", "sources"],
    )
