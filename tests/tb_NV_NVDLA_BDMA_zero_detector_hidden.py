# test_zero_detector.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10


@cocotb.test()
async def test_reset(dut):
    """Test basic reset behavior"""
    # Start the clock
    cocotb.start_soon(Clock(dut.nvdla_core_clk, CLK_PERIOD_NS, unit="ns").start())
    
    # Apply reset
    dut.nvdla_core_rstn.value = 0
    dut.nvdla_bdma_inp_data_pvld.value = 0
    dut.nvdla_bdma_inp_data_pd.value = 0
    dut.nvdla_bdma_out_data_prdy.value = 0
    dut.nvdla_bdma_out_blk_is_zero_rdy.value = 0
    dut.nvdla_bdma_reg2zd_cfg_enable.value = 0
    dut.nvdla_bdma_reg2zd_cfg_block_size.value = 0

    # Wait for reset to take effect
    await Timer(50, unit="ns")
    
    # Check that outputs are in reset state
    # Note: We don't check specific values as they might be X/Z in reset
    
    # Release reset
    dut.nvdla_core_rstn.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    await RisingEdge(dut.nvdla_core_clk)
    
    # After reset, check basic signal states
    # inp_data_prdy should be ready to accept data (or at least not X/Z)
    # out_data_pvld should be low (no valid output data)
    # out_blk_is_zero_vld should be low (no valid metadata)
    
    # Verify outputs are not asserting valid signals
    assert int(dut.nvdla_bdma_out_data_pvld.value) == 0, "Output data should not be valid after reset"
    assert int(dut.nvdla_bdma_out_blk_is_zero_vld.value) == 0, "Output metadata should not be valid after reset"
    
    cocotb.log.info("Reset test PASSED")
