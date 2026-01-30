`timescale 1ns/1ns
module NV_NVDLA_BDMA_zero_detector #(
    parameter int DATA_WIDTH   = 512,
    parameter int BLOCK_BEATS  = 16,
    parameter int CNT_WIDTH    = $clog2(BLOCK_BEATS + 1)
)(
    input  logic                      nvdla_core_clk,
    input  logic                      nvdla_core_rstn,

    // ------------------------------------------------------------
    // Configuration
    // ------------------------------------------------------------
    input  logic [1:0]                nvdla_bdma_reg2zd_cfg_block_size,
    input  logic                      nvdla_bdma_reg2zd_cfg_enable,

    // ------------------------------------------------------------
    // Input Stream Interface
    // ------------------------------------------------------------
    input  logic                      nvdla_bdma_inp_data_pvld,
    output logic                      nvdla_bdma_inp_data_prdy,
    input  logic [DATA_WIDTH-1:0]     nvdla_bdma_inp_data_pd,

    // ------------------------------------------------------------
    // Output Stream Interface
    // ------------------------------------------------------------
    output logic                      nvdla_bdma_out_data_pvld,
    input  logic                      nvdla_bdma_out_data_prdy,
    output logic [DATA_WIDTH-1:0]     nvdla_bdma_out_data_pd,

    // ------------------------------------------------------------
    // Block Result Interface
    // ------------------------------------------------------------
    output logic                      nvdla_bdma_out_blk_is_zero,
    output logic                      nvdla_bdma_out_blk_is_zero_vld,
    input  logic                      nvdla_bdma_out_blk_is_zero_rdy,

    // ------------------------------------------------------------
    // Status
    // ------------------------------------------------------------
    output logic                      nvdla_bdma_zd2reg_error_overflow
);

//insert logic

endmodule
