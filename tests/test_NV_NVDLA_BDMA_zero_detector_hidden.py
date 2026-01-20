# -*- coding: utf-8 -*-
# test_zero_detector.py
import sys
import cocotb
from cocotb.clock import Clock
import random
import os
from pathlib import Path
from collections import deque
from cocotb_tools.runner import get_runner
from cocotb.triggers import RisingEdge, Timer
import glob
from cocotb_test.simulator import run


# Set UTF-8 encoding for Python I/O operations
os.environ["PYTHONIOENCODING"] = "utf-8"

# Reconfigure stdout/stderr to use UTF-8 encoding (especially important on Windows)
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')


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


@cocotb.test()
async def test_reset_behavior(dut):
    """Test that reset properly initializes all outputs"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    
    # Apply reset
    dut.nvdla_core_rstn.value = 0
    await Timer(50, unit="ns")
    await RisingEdge(dut.nvdla_core_clk)
    
    # Check outputs are in reset state
    assert dut.nvdla_bdma_out_data_pvld.value == 0, "Output valid should be low in reset"
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata valid should be low in reset"
    assert dut.nvdla_bdma_zd2reg_error_overflow.value == 0, "Error should be low in reset"
    
    # Release reset
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # After reset, outputs should still be inactive until data is sent
    assert dut.nvdla_bdma_out_data_pvld.value == 0, "Output should remain inactive after reset"
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata should remain inactive after reset"
    
    cocotb.log.info("Reset behavior test PASSED")


@cocotb.test()
async def test_consecutive_zeros(dut):
    """Test multiple consecutive zero beats"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send 10 consecutive zero beats
    for i in range(10):
        await send_beat(dut, 0x00)
        out = await recv_data(dut)
        assert out == 0x00, f"Data mismatch on zero beat {i}: {out} != 0x00"
        
        meta = await recv_zero_meta(dut)
        assert meta == 1, f"Zero metadata mismatch on beat {i}: {meta} != 1"
    
    cocotb.log.info("Consecutive zeros test PASSED")


@cocotb.test()
async def test_consecutive_nonzeros(dut):
    """Test multiple consecutive non-zero beats"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send 10 consecutive non-zero beats with different values
    test_values = [0x01, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0xFF]
    
    for i, val in enumerate(test_values):
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Data mismatch on beat {i}: {out} != {val}"
        
        meta = await recv_zero_meta(dut)
        assert meta == 0, f"Zero metadata should be 0 for non-zero value 0x{val:02X} on beat {i}"
    
    cocotb.log.info("Consecutive non-zeros test PASSED")


@cocotb.test()
async def test_metadata_independence(dut):
    """Test that metadata handshake is independent of data handshake"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat
    await send_beat(dut, 0x42)
    
    # Accept data immediately
    out = await recv_data(dut)
    assert out == 0x42, f"Data mismatch: {out} != 0x42"
    
    # Wait several cycles before accepting metadata
    for _ in range(5):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should remain valid"
        assert dut.nvdla_bdma_out_blk_is_zero.value == 0, "Metadata should indicate non-zero"
    
    # Now accept metadata
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    cocotb.log.info("Metadata independence test PASSED")


@cocotb.test()
async def test_edge_cases(dut):
    """Test edge values (0x00, 0x01, 0xFE, 0xFF)"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    edge_cases = [
        (0x00, 1),  # Minimum value, zero
        (0x01, 0),  # Smallest non-zero
        (0xFE, 0),  # Largest non-zero
        (0xFF, 0),  # Maximum value, non-zero
    ]
    
    for val, expected_zero in edge_cases:
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Data mismatch for edge case 0x{val:02X}: {out} != {val}"
        
        meta = await recv_zero_meta(dut)
        assert meta == expected_zero, f"Zero metadata mismatch for 0x{val:02X}: {meta} != {expected_zero}"
    
    cocotb.log.info("Edge cases test PASSED")


@cocotb.test()
async def test_rapid_toggle(dut):
    """Test rapid enable/disable toggling"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    # Toggle enable multiple times
    for _ in range(5):
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
        await RisingEdge(dut.nvdla_core_clk)
        
        # Send a beat while enabled
        await send_beat(dut, 0xAA)
        out = await recv_data(dut)
        assert out == 0xAA, "Data should pass through"
        
        meta = await recv_zero_meta(dut)
        assert meta == 0, "Should detect non-zero"
        
        # Disable
        dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
        await RisingEdge(dut.nvdla_core_clk)
        
        # Verify metadata is cleared
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata should clear when disabled"
        
        # Send in bypass mode
        out = await send_recv_concurrent(dut, 0xBB)
        assert out == 0xBB, "Bypass should work"
    
    cocotb.log.info("Rapid toggle test PASSED")


@cocotb.test()
async def test_metadata_backpressure(dut):
    """Test backpressure on metadata channel"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat and accept data
    await send_beat(dut, 0x33)
    out = await recv_data(dut)
    assert out == 0x33, "Data should be received"
    
    # Apply backpressure on metadata (don't assert ready)
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    # Wait several cycles - metadata should remain valid
    for _ in range(8):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should remain valid under backpressure"
        assert dut.nvdla_bdma_out_blk_is_zero.value == 0, "Metadata value should remain stable"
    
    # Now accept metadata
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should still be valid"
    meta = int(dut.nvdla_bdma_out_blk_is_zero.value)
    assert meta == 0, "Should detect non-zero"
    
    # Complete handshake
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await RisingEdge(dut.nvdla_core_clk)
    
    cocotb.log.info("Metadata backpressure test PASSED")


@cocotb.test()
async def test_mixed_patterns(dut):
    """Test alternating zero/non-zero patterns"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Test alternating pattern
    pattern = [(0x00, 1), (0x11, 0), (0x00, 1), (0x22, 0), (0x00, 1), (0x33, 0)]
    
    for val, expected_zero in pattern:
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Data mismatch: {out} != {val}"
        
        meta = await recv_zero_meta(dut)
        assert meta == expected_zero, f"Zero metadata mismatch for 0x{val:02X}: {meta} != {expected_zero}"
    
    cocotb.log.info("Mixed patterns test PASSED")


@cocotb.test()
async def test_all_byte_values(dut):
    """Test systematic coverage of all 8-bit values"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Test every 16th value to cover the space efficiently
    for val in range(0, 256, 16):
        await send_beat(dut, val)
        out = await recv_data(dut)
        assert out == val, f"Data mismatch for 0x{val:02X}: {out} != {val}"
        
        meta = await recv_zero_meta(dut)
        expected_zero = 1 if val == 0 else 0
        assert meta == expected_zero, f"Zero metadata mismatch for 0x{val:02X}: {meta} != {expected_zero}"
    
    cocotb.log.info("All byte values test PASSED")


@cocotb.test()
async def test_input_ready_deasserted(dut):
    """Corner case: Input ready deasserted during transfer attempt"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Try to send but input ready might be deasserted
    dut.nvdla_bdma_inp_data_pd.value = 0x55
    dut.nvdla_bdma_inp_data_pvld.value = 1
    
    # Wait a few cycles - module might not accept immediately
    for _ in range(3):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            break
    
    # If accepted, complete the transfer
    if dut.nvdla_bdma_inp_data_prdy.value:
        dut.nvdla_bdma_inp_data_pvld.value = 0
        await recv_data(dut)
        await recv_zero_meta(dut)
    
    cocotb.log.info("Input ready deasserted test PASSED")


@cocotb.test()
async def test_enable_during_transfer(dut):
    """Corner case: Enable toggled during active data transfer"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    # Start disabled
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    
    # Send a beat in bypass mode
    await send_beat(dut, 0xAA)
    
    # Toggle enable while data is in flight
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Receive data (should still be valid)
    out = await recv_data(dut)
    assert out == 0xAA, "Data should be received even if enable changed"
    
    # Next beat should have metadata
    await send_beat(dut, 0xBB)
    out = await recv_data(dut)
    assert out == 0xBB, "Data should pass through"
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    cocotb.log.info("Enable during transfer test PASSED")


@cocotb.test()
async def test_reset_during_operation(dut):
    """Corner case: Reset asserted during active operation"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat
    await send_beat(dut, 0x77)
    
    # Assert reset while data is in flight
    dut.nvdla_core_rstn.value = 0
    await Timer(50, unit="ns")
    await RisingEdge(dut.nvdla_core_clk)
    
    # Verify outputs are in reset state
    assert dut.nvdla_bdma_out_data_pvld.value == 0, "Output should be reset"
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "Metadata should be reset"
    
    # Release reset
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Module should be ready for new data
    assert dut.nvdla_bdma_out_data_pvld.value == 0, "Output should be inactive after reset"
    
    cocotb.log.info("Reset during operation test PASSED")


@cocotb.test()
async def test_multiple_beats_before_consume(dut):
    """Corner case: Multiple beats sent before consuming any output"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send multiple beats without consuming
    # Note: This test assumes the module can buffer at least one beat
    # If not, the module should backpressure on input
    for i in range(3):
        dut.nvdla_bdma_inp_data_pd.value = 0x10 + i
        dut.nvdla_bdma_inp_data_pvld.value = 1
        
        # Wait for acceptance or backpressure
        cycles = 0
        while not dut.nvdla_bdma_inp_data_prdy.value and cycles < 10:
            await RisingEdge(dut.nvdla_core_clk)
            cycles += 1
        
        if dut.nvdla_bdma_inp_data_prdy.value:
            dut.nvdla_bdma_inp_data_pvld.value = 0
            await RisingEdge(dut.nvdla_core_clk)
        else:
            # Module is backpressuring, consume one output
            if dut.nvdla_bdma_out_data_pvld.value:
                await recv_data(dut)
                await recv_zero_meta(dut)
    
    # Consume remaining outputs
    while dut.nvdla_bdma_out_data_pvld.value:
        await recv_data(dut)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            await recv_zero_meta(dut)
        await RisingEdge(dut.nvdla_core_clk)
    
    cocotb.log.info("Multiple beats before consume test PASSED")


@cocotb.test()
async def test_metadata_ready_timing(dut):
    """Corner case: Metadata ready deasserted and reasserted"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat
    await send_beat(dut, 0x88)
    await recv_data(dut)
    
    # Metadata should be valid
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should be valid"
    
    # Deassert ready
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    await RisingEdge(dut.nvdla_core_clk)
    
    # Metadata should remain valid
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should remain valid"
    
    # Reassert ready
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Handshake should complete
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0 or dut.nvdla_bdma_out_blk_is_zero_rdy.value == 0, "Handshake should complete"
    
    cocotb.log.info("Metadata ready timing test PASSED")


@cocotb.test()
async def test_simultaneous_backpressure(dut):
    """Corner case: Simultaneous backpressure on both data and metadata channels"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat
    await send_beat(dut, 0x99)
    
    # Apply backpressure on both channels
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    # Wait several cycles
    for _ in range(5):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 1, "Data should remain valid"
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should remain valid"
    
    # Release data backpressure first
    dut.nvdla_bdma_out_data_prdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Data should be consumed
    data = int(dut.nvdla_bdma_out_data_pd.value)
    assert data == 0x99, "Data should be correct"
    dut.nvdla_bdma_out_data_prdy.value = 0
    
    # Metadata should still be valid
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 1, "Metadata should still be valid"
    
    # Now release metadata backpressure
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    meta = int(dut.nvdla_bdma_out_blk_is_zero.value)
    assert meta == 0, "Should detect non-zero"
    
    cocotb.log.info("Simultaneous backpressure test PASSED")


@cocotb.test()
async def test_enable_between_beats(dut):
    """Corner case: Enable changed between consecutive beats"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    # First beat with enable=1
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await send_beat(dut, 0x11)
    out = await recv_data(dut)
    assert out == 0x11, "Data should pass through"
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    # Disable between beats
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)
    
    # Second beat with enable=0 (bypass)
    out = await send_recv_concurrent(dut, 0x22)
    assert out == 0x22, "Bypass should work"
    assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "No metadata in bypass"
    
    # Re-enable
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    # Third beat with enable=1 again
    await send_beat(dut, 0x00)
    out = await recv_data(dut)
    assert out == 0x00, "Data should pass through"
    meta = await recv_zero_meta(dut)
    assert meta == 1, "Should detect zero"
    
    cocotb.log.info("Enable between beats test PASSED")


@cocotb.test()
async def test_empty_sequence(dut):
    """Corner case: No data sent, just enable/disable"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    # Enable without sending data
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    for _ in range(10):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 0, "No output without input"
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "No metadata without input"
    
    # Disable
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    for _ in range(10):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 0, "No output without input"
        assert dut.nvdla_bdma_out_blk_is_zero_vld.value == 0, "No metadata without input"
    
    cocotb.log.info("Empty sequence test PASSED")


@cocotb.test()
async def test_config_change_during_operation(dut):
    """Corner case: Configuration (block_size) changed during operation"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0
    
    # Send a beat
    await send_beat(dut, 0x44)
    
    # Change block_size during operation (should not affect per-beat operation)
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 3
    await RisingEdge(dut.nvdla_core_clk)
    
    # Complete the transfer
    out = await recv_data(dut)
    assert out == 0x44, "Data should be received"
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    # Send another beat with new config
    await send_beat(dut, 0x55)
    out = await recv_data(dut)
    assert out == 0x55, "Data should be received"
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    cocotb.log.info("Config change during operation test PASSED")


@cocotb.test()
async def test_rapid_sequential_beats(dut):
    """Corner case: Rapid sequential beats with minimal delay"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Keep output ready asserted to allow rapid flow
    dut.nvdla_bdma_out_data_prdy.value = 1
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    
    # Send rapid sequential beats
    test_values = [0x01, 0x02, 0x03, 0x04, 0x05]
    received_data = []
    received_meta = []
    
    for val in test_values:
        await send_beat(dut, val)
        # Data should be available quickly
        if dut.nvdla_bdma_out_data_pvld.value:
            data = int(dut.nvdla_bdma_out_data_pd.value)
            received_data.append(data)
            await RisingEdge(dut.nvdla_core_clk)
            
            # Metadata should follow
            if dut.nvdla_bdma_out_blk_is_zero_vld.value:
                meta = int(dut.nvdla_bdma_out_blk_is_zero.value)
                received_meta.append(meta)
                await RisingEdge(dut.nvdla_core_clk)
    
    # Verify all data was received correctly
    assert len(received_data) == len(test_values), "All data should be received"
    for i, val in enumerate(test_values):
        assert received_data[i] == val, f"Data mismatch at index {i}"
        assert received_meta[i] == 0, f"All values should be non-zero"
    
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    cocotb.log.info("Rapid sequential beats test PASSED")


@cocotb.test()
async def test_input_ready_timeout(dut):
    """Timeout condition: Input ready never asserts (module backpressuring)"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Try to send data but keep output not ready to cause backpressure
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    # Send first beat (should be accepted)
    await send_beat(dut, 0xAA)
    
    # Now try to send second beat - module should backpressure
    dut.nvdla_bdma_inp_data_pd.value = 0xBB
    dut.nvdla_bdma_inp_data_pvld.value = 1
    
    # Wait with timeout - ready should not assert
    timeout_cycles = 20
    ready_asserted = False
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            ready_asserted = True
            break
    
    # Module should backpressure (ready not asserted) if output is not consumed
    # This is expected behavior - not a failure
    if not ready_asserted:
        cocotb.log.info("Input backpressure detected (expected behavior)")
        dut.nvdla_bdma_inp_data_pvld.value = 0
        
        # Consume output to release backpressure
        if dut.nvdla_bdma_out_data_pvld.value:
            await recv_data(dut)
            await recv_zero_meta(dut)
        
        # Now input should be ready
        dut.nvdla_bdma_inp_data_pvld.value = 1
        cycles = 0
        while not dut.nvdla_bdma_inp_data_prdy.value and cycles < 10:
            await RisingEdge(dut.nvdla_core_clk)
            cycles += 1
        
        assert dut.nvdla_bdma_inp_data_prdy.value or cycles < 10, "Input should be ready after consuming output"
    
    cocotb.log.info("Input ready timeout test PASSED")


@cocotb.test()
async def test_output_valid_timeout(dut):
    """Timeout condition: Output valid never asserts after sending data"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat
    await send_beat(dut, 0xCC)
    
    # Wait for output valid with timeout
    timeout_cycles = 50
    valid_asserted = False
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            valid_asserted = True
            break
    
    # Output valid should assert within reasonable time (module has 1-cycle latency)
    assert valid_asserted, f"Output valid should assert within {timeout_cycles} cycles"
    
    # Verify data is correct
    assert int(dut.nvdla_bdma_out_data_pd.value) == 0xCC, "Output data should match input"
    
    cocotb.log.info("Output valid timeout test PASSED")


@cocotb.test()
async def test_metadata_valid_timeout(dut):
    """Timeout condition: Metadata valid never asserts after data transfer"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send a beat and consume data
    await send_beat(dut, 0xDD)
    await recv_data(dut)
    
    # Wait for metadata valid with timeout
    timeout_cycles = 50
    valid_asserted = False
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_blk_is_zero_vld.value:
            valid_asserted = True
            break
    
    # Metadata valid should assert within reasonable time
    assert valid_asserted, f"Metadata valid should assert within {timeout_cycles} cycles"
    
    # Verify metadata is correct
    assert int(dut.nvdla_bdma_out_blk_is_zero.value) == 0, "Should detect non-zero"
    
    cocotb.log.info("Metadata valid timeout test PASSED")


@cocotb.test()
async def test_handshake_timeout_recovery(dut):
    """Timeout condition: Timeout followed by recovery"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Create backpressure situation
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    # Send first beat
    await send_beat(dut, 0xEE)
    
    # Wait for output (should assert quickly)
    timeout_cycles = 10
    output_ready = False
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            output_ready = True
            break
    
    assert output_ready, "Output should be valid"
    
    # Wait longer (simulating timeout scenario)
    for _ in range(20):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 1, "Output should remain valid"
    
    # Recover by accepting output
    dut.nvdla_bdma_out_data_prdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    data = int(dut.nvdla_bdma_out_data_pd.value)
    assert data == 0xEE, "Data should be correct after recovery"
    dut.nvdla_bdma_out_data_prdy.value = 0
    
    # Accept metadata
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    meta = int(dut.nvdla_bdma_out_blk_is_zero.value)
    assert meta == 0, "Metadata should be correct"
    
    cocotb.log.info("Handshake timeout recovery test PASSED")


@cocotb.test()
async def test_deadlock_detection(dut):
    """Timeout condition: Detect potential deadlock scenarios"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Scenario: Input valid but output not ready, and output valid but input not ready
    # This should not cause deadlock - module should handle backpressure correctly
    
    # Send first beat
    await send_beat(dut, 0xF0)
    
    # Apply backpressure on output
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    
    # Wait - output should remain valid
    for _ in range(15):
        await RisingEdge(dut.nvdla_core_clk)
        assert dut.nvdla_bdma_out_data_pvld.value == 1, "Output should remain valid under backpressure"
    
    # Input should be backpressured (ready should be 0)
    dut.nvdla_bdma_inp_data_pd.value = 0xF1
    dut.nvdla_bdma_inp_data_pvld.value = 1
    
    # Check for deadlock - input ready should be 0 (backpressured)
    for _ in range(5):
        await RisingEdge(dut.nvdla_core_clk)
        # Input ready should be 0 (module is backpressured)
        # This is not a deadlock, just normal backpressure
    
    # Release deadlock by consuming output
    dut.nvdla_bdma_out_data_prdy.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    data = int(dut.nvdla_bdma_out_data_pd.value)
    assert data == 0xF0, "First beat should be received"
    dut.nvdla_bdma_out_data_prdy.value = 0
    
    # Now input should be ready
    cycles = 0
    while not dut.nvdla_bdma_inp_data_prdy.value and cycles < 10:
        await RisingEdge(dut.nvdla_core_clk)
        cycles += 1
    
    assert dut.nvdla_bdma_inp_data_prdy.value or cycles < 10, "Input should be ready after consuming output"
    
    cocotb.log.info("Deadlock detection test PASSED")


@cocotb.test()
async def test_metadata_timeout_with_data_consumed(dut):
    """Timeout condition: Metadata timeout after data is consumed"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Send and consume data immediately
    await send_beat(dut, 0x11)
    await recv_data(dut)
    
    # Don't consume metadata - wait to see if it times out or remains valid
    timeout_cycles = 30
    metadata_still_valid = True
    
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if not dut.nvdla_bdma_out_blk_is_zero_vld.value:
            metadata_still_valid = False
            break
    
    # Metadata should remain valid until consumed (no timeout)
    assert metadata_still_valid, "Metadata should remain valid until consumed"
    
    # Now consume it
    meta = await recv_zero_meta(dut)
    assert meta == 0, "Should detect non-zero"
    
    cocotb.log.info("Metadata timeout with data consumed test PASSED")


@cocotb.test()
async def test_bypass_timeout_behavior(dut):
    """Timeout condition: Timeout behavior in bypass mode"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0  # Bypass mode
    
    # In bypass mode, data should flow immediately
    dut.nvdla_bdma_inp_data_pd.value = 0x22
    dut.nvdla_bdma_inp_data_pvld.value = 1
    dut.nvdla_bdma_out_data_prdy.value = 1
    
    # Wait for handshake with timeout
    timeout_cycles = 20
    handshake_complete = False
    
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value and dut.nvdla_bdma_out_data_pvld.value:
            handshake_complete = True
            data = int(dut.nvdla_bdma_out_data_pd.value)
            assert data == 0x22, "Data should match in bypass mode"
            break
    
    assert handshake_complete, f"Bypass handshake should complete within {timeout_cycles} cycles"
    
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    
    cocotb.log.info("Bypass timeout behavior test PASSED")


@cocotb.test()
async def test_consecutive_timeouts(dut):
    """Timeout condition: Multiple consecutive timeout scenarios"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Create multiple timeout scenarios
    for i in range(3):
        # Apply backpressure
        dut.nvdla_bdma_out_data_prdy.value = 0
        dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
        
        # Send beat
        await send_beat(dut, 0x30 + i)
        
        # Wait for output (should appear quickly)
        timeout_cycles = 10
        output_valid = False
        for _ in range(timeout_cycles):
            await RisingEdge(dut.nvdla_core_clk)
            if dut.nvdla_bdma_out_data_pvld.value:
                output_valid = True
                break
        
        assert output_valid, f"Output should be valid for beat {i}"
        
        # Wait longer (simulating timeout)
        for _ in range(10):
            await RisingEdge(dut.nvdla_core_clk)
            assert dut.nvdla_bdma_out_data_pvld.value == 1, f"Output should remain valid for beat {i}"
        
        # Recover
        await recv_data(dut)
        await recv_zero_meta(dut)
    
    cocotb.log.info("Consecutive timeouts test PASSED")


@cocotb.test()
async def test_timeout_after_reset(dut):
    """Timeout condition: Timeout behavior immediately after reset"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    
    # Reset
    dut.nvdla_core_rstn.value = 0
    await Timer(50, unit="ns")
    await RisingEdge(dut.nvdla_core_clk)
    
    # Release reset
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 1
    
    # Immediately try to send data
    dut.nvdla_bdma_inp_data_pd.value = 0x44
    dut.nvdla_bdma_inp_data_pvld.value = 1
    
    # Wait for ready with timeout
    timeout_cycles = 20
    ready_asserted = False
    
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_inp_data_prdy.value:
            ready_asserted = True
            break
    
    # After reset, module should be ready to accept data
    assert ready_asserted, "Module should be ready after reset"
    
    dut.nvdla_bdma_inp_data_pvld.value = 0
    
    # Wait for output
    timeout_cycles = 20
    output_valid = False
    for _ in range(timeout_cycles):
        await RisingEdge(dut.nvdla_core_clk)
        if dut.nvdla_bdma_out_data_pvld.value:
            output_valid = True
            break
    
    assert output_valid, "Output should be valid after reset"
    
    cocotb.log.info("Timeout after reset test PASSED")


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
