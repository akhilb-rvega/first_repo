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

# Block size configurations
BLOCK_SIZE_16 = 0
BLOCK_SIZE_32 = 1
BLOCK_SIZE_64 = 2
BLOCK_SIZE_128 = 3

# FSM States (from RTL)
ZD_STATE_IDLE = 0
ZD_STATE_DETECTING = 1
ZD_STATE_BLOCK_DONE = 2
ZD_STATE_ERROR = 3


class ZeroDetectorDriver:
    """Driver for zero detector input data stream"""
    
    def __init__(self, dut):
        self.dut = dut
        self.dut.inp_data_pvld.value = 0
        self.dut.inp_data_pd.value = 0
    
    async def send_data(self, data, delay=0):
        """Send a data word on the input stream (512-bit)"""
        if delay > 0:
            await Timer(delay, units="ns")
        
        # Handle 512-bit data - cocotb can handle large integers
        self.dut.inp_data_pd.value = data
        self.dut.inp_data_pvld.value = 1
        
        await ReadWrite()
        while self.dut.inp_data_prdy.value == 0:
            await RisingEdge(self.dut.nvdla_core_clk)
        
        await RisingEdge(self.dut.nvdla_core_clk)
        self.dut.inp_data_pvld.value = 0
        await Timer(1, units="ns")
    
    async def send_block(self, data_list, delay=0):
        """Send a complete block of data"""
        for data in data_list:
            await self.send_data(data, delay)


class ZeroDetectorMonitor:
    """Monitor for zero detector output data stream and block results"""
    
    def __init__(self, dut):
        self.dut = dut
        self.dut.out_data_prdy.value = 1
        self.dut.out_blk_is_zero_rdy.value = 1
        self.received_data = []
        self.received_block_results = []
    
    async def monitor_data(self):
        """Monitor output data stream"""
        while True:
            await RisingEdge(self.dut.nvdla_core_clk)
            if self.dut.out_data_pvld.value == 1 and self.dut.out_data_prdy.value == 1:
                # Get 512-bit value (cocotb handles large integers)
                val = self.dut.out_data_pd.value
                self.received_data.append(int(val))
    
    async def monitor_block_results(self):
        """Monitor block-level zero detection results"""
        while True:
            await RisingEdge(self.dut.nvdla_core_clk)
            if self.dut.out_blk_is_zero_vld.value == 1 and self.dut.out_blk_is_zero_rdy.value == 1:
                result = {
                    'is_zero': bool(self.dut.out_blk_is_zero.value),
                    'cycle': cocotb.utils.get_sim_time('ns')
                }
                self.received_block_results.append(result)


@cocotb.test()
async def test_reset(dut):
    """Test reset behavior"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    # Reset
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 0
    dut.reg2zd_cfg_block_size.value = 0
    await Timer(20, units="ns")
    
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    await Timer(5, units="ns")
    
    # Check reset values
    assert dut.out_data_pvld.value == 0, "Output valid should be 0 after reset"
    assert dut.out_blk_is_zero_vld.value == 0, "Block result valid should be 0 after reset"
    assert dut.zd2reg_error_overflow.value == 0, "Error should be 0 after reset"


@cocotb.test()
async def test_bypass_mode(dut):
    """Test bypass mode - data should pass through transparently"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 0  # Bypass mode
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    
    # Send some data (512-bit values)
    test_data = [
        0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF,
        0xDEADBEEFCAFEBABEDEADBEEFCAFEBABEDEADBEEFCAFEBABEDEADBEEFCAFEBABE,
        0xFFFFFFFF00000000FFFFFFFF00000000FFFFFFFF00000000FFFFFFFF00000000
    ]
    
    for data in test_data:
        await driver.send_data(data)
        await RisingEdge(dut.nvdla_core_clk)
        await Timer(1, units="ns")
        # In bypass mode, output should match input immediately
        out_val = int(dut.out_data_pd.value)
        assert out_val == data, f"Bypass mode: output should match input {hex(data)}, got {hex(out_val)}"
        assert dut.out_data_pvld.value == 1, "Bypass mode: output should be valid"
    
    # Block results should not be generated in bypass mode
    await Timer(100, units="ns")
    assert len(monitor.received_block_results) == 0, "No block results in bypass mode"


@cocotb.test()
async def test_all_zero_block_16(dut):
    """Test detection of all-zero block with block size 16"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send 16 beats of all zeros
    zero_data = [0] * 16
    await driver.send_block(zero_data)
    
    # Wait for block result
    await Timer(200, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Should have one block result"
    assert monitor.received_block_results[0]['is_zero'] == True, "Block should be detected as all zeros"


@cocotb.test()
async def test_non_zero_block_16(dut):
    """Test detection of non-zero block with block size 16"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send 16 beats: first 15 zeros, last one non-zero (512-bit)
    block_data = [0] * 15 + [0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF]
    await driver.send_block(block_data)
    
    # Wait for block result
    await Timer(200, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Should have one block result"
    assert monitor.received_block_results[0]['is_zero'] == False, "Block should be detected as non-zero"


@cocotb.test()
async def test_block_size_32(dut):
    """Test with block size 32"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_32
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send 32 beats of all zeros
    zero_data = [0] * 32
    await driver.send_block(zero_data)
    
    await Timer(400, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Should have one block result for 32-beat block"
    assert monitor.received_block_results[0]['is_zero'] == True, "32-beat block should be detected as all zeros"


@cocotb.test()
async def test_block_size_64(dut):
    """Test with block size 64"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_64
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send 64 beats: all zeros except one (512-bit)
    block_data = [0] * 32 + [0xDEADBEEFCAFEBABEDEADBEEFCAFEBABEDEADBEEFCAFEBABEDEADBEEFCAFEBABE] + [0] * 31
    await driver.send_block(block_data)
    
    await Timer(800, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Should have one block result for 64-beat block"
    assert monitor.received_block_results[0]['is_zero'] == False, "64-beat block with non-zero should be detected"


@cocotb.test()
async def test_multiple_blocks(dut):
    """Test multiple consecutive blocks"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send 3 blocks: zero, non-zero, zero (512-bit)
    block1 = [0] * 16
    block2 = [0] * 15 + [0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF]
    block3 = [0] * 16
    
    await driver.send_block(block1)
    await Timer(50, units="ns")
    
    await driver.send_block(block2)
    await Timer(50, units="ns")
    
    await driver.send_block(block3)
    await Timer(200, units="ns")
    
    assert len(monitor.received_block_results) == 3, "Should have 3 block results"
    assert monitor.received_block_results[0]['is_zero'] == True, "First block should be zero"
    assert monitor.received_block_results[1]['is_zero'] == False, "Second block should be non-zero"
    assert monitor.received_block_results[2]['is_zero'] == True, "Third block should be zero"


@cocotb.test()
async def test_early_nonzero_detection(dut):
    """Test that non-zero detection works even if non-zero appears early"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send block with non-zero in first beat (512-bit)
    block_data = [0xABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890] + [0] * 15
    await driver.send_block(block_data)
    
    await Timer(200, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Should have one block result"
    assert monitor.received_block_results[0]['is_zero'] == False, "Block with early non-zero should be detected"


@cocotb.test()
async def test_data_pass_through(dut):
    """Test that data passes through correctly while detecting"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    
    # Send block with known data (512-bit)
    test_data = [
        0x1111111111111111111111111111111111111111111111111111111111111111,
        0x2222222222222222222222222222222222222222222222222222222222222222,
        0x3333333333333333333333333333333333333333333333333333333333333333,
        0x4444444444444444444444444444444444444444444444444444444444444444
    ] + [0] * 12
    await driver.send_block(test_data)
    
    await Timer(200, units="ns")
    
    # Check that all data was received
    assert len(monitor.received_data) == 16, "Should receive all 16 data words"
    for i, expected in enumerate(test_data):
        assert monitor.received_data[i] == expected, f"Data word {i} should match input"


@cocotb.test()
async def test_backpressure(dut):
    """Test backpressure handling - output not ready"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Apply backpressure
    dut.out_data_prdy.value = 0
    
    # Try to send data
    block_data = [0] * 16
    for i, data in enumerate(block_data):
        dut.inp_data_pd.value = data
        dut.inp_data_pd.value = data
        dut.inp_data_pvld.value = 1
        await RisingEdge(dut.nvdla_core_clk)
        # Input should not be ready when output is not ready
        if i < 15:  # Don't check on last beat as state may change
            assert dut.inp_data_prdy.value == 0, f"Input should not be ready when output not ready (beat {i})"
    
    # Release backpressure
    dut.out_data_prdy.value = 1
    dut.inp_data_pvld.value = 0
    await Timer(200, units="ns")
    
    # Should eventually get results
    assert len(monitor.received_data) > 0, "Should receive data after backpressure release"


@cocotb.test()
async def test_block_result_backpressure(dut):
    """Test backpressure on block result output"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Apply backpressure on block result
    dut.out_blk_is_zero_rdy.value = 0
    
    # Send a block
    block_data = [0] * 16
    await driver.send_block(block_data)
    
    await Timer(100, units="ns")
    
    # Block result should be valid but not accepted
    assert dut.out_blk_is_zero_vld.value == 1, "Block result should be valid"
    assert len(monitor.received_block_results) == 0, "Block result should not be accepted yet"
    
    # Release backpressure
    dut.out_blk_is_zero_rdy.value = 1
    await Timer(50, units="ns")
    
    assert len(monitor.received_block_results) == 1, "Block result should be accepted after backpressure release"


@cocotb.test()
async def test_disable_clears_state(dut):
    """Test that disabling clears the state"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Send partial block (8 beats)
    partial_block = [0] * 8
    await driver.send_block(partial_block)
    await Timer(50, units="ns")
    
    # Disable zero detection
    dut.reg2zd_cfg_enable.value = 0
    await RisingEdge(dut.nvdla_core_clk)
    await Timer(20, units="ns")
    
    # Should not have block result (block was incomplete)
    assert len(monitor.received_block_results) == 0, "Should not have block result for incomplete block"
    
    # Should be in bypass mode now (512-bit)
    test_data = 0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF
    await driver.send_data(test_data)
    await RisingEdge(dut.nvdla_core_clk)
    out_val = int(dut.out_data_pd.value)
    assert out_val == test_data, f"Should pass through in bypass mode: expected {hex(test_data)}, got {hex(out_val)}"


@cocotb.test()
async def test_random_data(dut):
    """Test with random data patterns"""
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, units="ns").start())
    
    dut.nvdla_core_rstn.value = 0
    dut.reg2zd_cfg_enable.value = 1
    dut.reg2zd_cfg_block_size.value = BLOCK_SIZE_16
    await Timer(20, units="ns")
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    
    driver = ZeroDetectorDriver(dut)
    monitor = ZeroDetectorMonitor(dut)
    cocotb.start_soon(monitor.monitor_data())
    cocotb.start_soon(monitor.monitor_block_results())
    
    # Generate random blocks (512-bit)
    random.seed(42)
    for block_num in range(5):
        # Random block: mostly zeros with some non-zero (512-bit values)
        block_data = []
        for _ in range(16):
            if random.random() < 0.1:
                # Generate random 512-bit value
                val = random.randint(0, (1 << 512) - 1)
                block_data.append(val)
            else:
                block_data.append(0)
        is_all_zero = all(x == 0 for x in block_data)
        
        await driver.send_block(block_data)
        await Timer(200, units="ns")
        
        if len(monitor.received_block_results) > block_num:
            expected = is_all_zero
            actual = monitor.received_block_results[block_num]['is_zero']
            assert actual == expected, f"Block {block_num}: expected is_zero={expected}, got {actual}"


# ✅ REQUIRED: Pytest wrapper function
def test_tb_NV_NVDLA_BDMA_zero_detector_runner():
    """Pytest wrapper for cocotb testbench"""
    import os
    from pathlib import Path
    
    # Try to import runner from cocotb_tools (Cocotb 1.8+)
    try:
        from cocotb_tools.runner import get_runner
    except ImportError:
        # Fallback for older Cocotb versions or if cocotb-tools is not installed
        try:
            from cocotb.runner import get_runner
        except ImportError:
            raise ImportError(
                "Could not import get_runner from cocotb_tools.runner or cocotb.runner.\n"
                "Please install cocotb-tools: pip install cocotb-tools\n"
                "Or ensure you have Cocotb 1.8+ installed: pip install cocotb"
            )
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [
        proj_path / "sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v",
    ]
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        always=True,
    )
    
    runner.test(
        hdl_toplevel="NV_NVDLA_BDMA_zero_detector",
        test_module="tb_NV_NVDLA_BDMA_zero_detector_hidden"
    )


if __name__ == "__main__":
    # For standalone execution
    test_tb_NV_NVDLA_BDMA_zero_detector_runner()



