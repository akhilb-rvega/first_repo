// ================================================================
//  NV_NVDLA_BDMA_zero_detector (NO beat_cnt VERSION)
// ================================================================
`timescale 1ns/1ns
module NV_NVDLA_BDMA_zero_detector (
    input  wire        nvdla_core_clk,
    input  wire        nvdla_core_rstn,

    // Configuration
    input  wire [1:0]  nvdla_bdma_reg2zd_cfg_block_size, // unused
    input  wire        nvdla_bdma_reg2zd_cfg_enable,

    // Error reporting (unused, tied low)
    output reg         nvdla_bdma_zd2reg_error_overflow,

    // Input stream
    input  wire [7:0]  nvdla_bdma_inp_data_pd,
    input  wire        nvdla_bdma_inp_data_pvld,
    output wire        nvdla_bdma_inp_data_prdy,

    // Output stream
    output wire [7:0]  nvdla_bdma_out_data_pd,
    output wire        nvdla_bdma_out_data_pvld,
    input  wire        nvdla_bdma_out_data_prdy,

    // Block result
    output reg         nvdla_bdma_out_blk_is_zero,
    output reg         nvdla_bdma_out_blk_is_zero_vld,
    input  wire        nvdla_bdma_out_blk_is_zero_rdy
);

 // insert logic

endmodule
