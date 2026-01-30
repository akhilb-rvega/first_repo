`timescale 1ns/1ns

module NV_NVDLA_BDMA_zero_detector #(
    parameter int DATA_WIDTH   = 512,
    parameter int BLOCK_BEATS  = 16,
    parameter int CNT_WIDTH    = $clog2(BLOCK_BEATS + 1)
)(
    input  logic                      nvdla_core_clk,
    input  logic                      nvdla_core_rstn,

    input  logic [1:0]                nvdla_bdma_reg2zd_cfg_block_size,
    input  logic                      nvdla_bdma_reg2zd_cfg_enable,

    input  logic                      nvdla_bdma_inp_data_pvld,
    output logic                      nvdla_bdma_inp_data_prdy,
    input  logic [DATA_WIDTH-1:0]     nvdla_bdma_inp_data_pd,

    output logic                      nvdla_bdma_out_data_pvld,
    input  logic                      nvdla_bdma_out_data_prdy,
    output logic [DATA_WIDTH-1:0]     nvdla_bdma_out_data_pd,

    output logic                      nvdla_bdma_out_blk_is_zero,
    output logic                      nvdla_bdma_out_blk_is_zero_vld,
    input  logic                      nvdla_bdma_out_blk_is_zero_rdy,

    output logic                      nvdla_bdma_zd2reg_error_overflow
);

    // ------------------------------------------------------------
    // Block size decode
    // ------------------------------------------------------------

    logic [CNT_WIDTH-1:0] block_beats;

    always_comb begin
        case (nvdla_bdma_reg2zd_cfg_block_size)
            2'd0: block_beats = 16;
            2'd1: block_beats = 32;
            2'd2: block_beats = 64;
            2'd3: block_beats = 128;
        endcase
    end

    // ------------------------------------------------------------
    // RAW input handshake (block logic)
    // ------------------------------------------------------------

    wire fire_in = nvdla_bdma_inp_data_pvld & nvdla_bdma_reg2zd_cfg_enable;

    assign nvdla_bdma_inp_data_prdy = nvdla_bdma_reg2zd_cfg_enable;

    // ------------------------------------------------------------
    // Output skid buffer
    // ------------------------------------------------------------

    logic skid_valid;

    always_ff @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            skid_valid <= 1'b0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            skid_valid <= 1'b0;
        else if (fire_in)
            skid_valid <= 1'b1;
        else if (nvdla_bdma_out_data_prdy)
            skid_valid <= 1'b0;
    end

    assign nvdla_bdma_out_data_pvld = skid_valid;

    always_ff @(posedge nvdla_core_clk) begin
        if (fire_in)
            nvdla_bdma_out_data_pd <= nvdla_bdma_inp_data_pd;
    end

    // ------------------------------------------------------------
    // Beat counter
    // ------------------------------------------------------------

    logic [CNT_WIDTH-1:0] beat_cnt;

    always_ff @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            beat_cnt <= 0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            beat_cnt <= 0;
        else if (fire_in) begin
            if (beat_cnt == block_beats - 1)
                beat_cnt <= 0;
            else
                beat_cnt <= beat_cnt + 1'b1;
        end
    end

    wire block_done = fire_in && (beat_cnt == block_beats - 1);

    // ------------------------------------------------------------
    // Zero accumulation
    // ------------------------------------------------------------

    wire data_is_zero = ~(|nvdla_bdma_inp_data_pd);
    logic any_nonzero;

    wire next_any_nonzero = any_nonzero | ~data_is_zero;

    always_ff @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            any_nonzero <= 1'b0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            any_nonzero <= 1'b0;
        else if (fire_in) begin
            if (block_done)
                any_nonzero <= 1'b0;
            else
                any_nonzero <= next_any_nonzero;
        end
    end

    // ------------------------------------------------------------
    // Block result generation (golden timing)
    // ------------------------------------------------------------

    always_ff @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
        else if (block_done)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
        else if (nvdla_bdma_out_blk_is_zero_vld &&
                 nvdla_bdma_out_blk_is_zero_rdy)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
    end

    always_ff @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_blk_is_zero <= 1'b0;
        else if (block_done)
            nvdla_bdma_out_blk_is_zero <= ~next_any_nonzero;
    end

    // ------------------------------------------------------------
    // Overflow must never assert
    // ------------------------------------------------------------

    assign nvdla_bdma_zd2reg_error_overflow = 1'b0;

endmodule
