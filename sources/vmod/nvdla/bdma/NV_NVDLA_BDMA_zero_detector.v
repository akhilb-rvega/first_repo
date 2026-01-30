`timescale 1ns/1ns

module NV_NVDLA_BDMA_zero_detector (

    input                      nvdla_core_clk,
    input                      nvdla_core_rstn,

    input      [1:0]           nvdla_bdma_reg2zd_cfg_block_size,
    input                      nvdla_bdma_reg2zd_cfg_enable,

    input                      nvdla_bdma_inp_data_pvld,
    output                     nvdla_bdma_inp_data_prdy,
    input      [511:0]         nvdla_bdma_inp_data_pd,

    output reg                 nvdla_bdma_out_data_pvld,
    input                      nvdla_bdma_out_data_prdy,
    output reg [511:0]         nvdla_bdma_out_data_pd,

    output reg                 nvdla_bdma_out_blk_is_zero,
    output reg                 nvdla_bdma_out_blk_is_zero_vld,
    input                      nvdla_bdma_out_blk_is_zero_rdy,

    output                     nvdla_bdma_zd2reg_error_overflow
);

    // ============================================================
    // Block size decode
    // ============================================================

    reg [7:0] block_beats;

    always @(*) begin
        case (nvdla_bdma_reg2zd_cfg_block_size)
            2'd0: block_beats = 8'd16;
            2'd1: block_beats = 8'd32;
            2'd2: block_beats = 8'd64;
            2'd3: block_beats = 8'd128;
            default: block_beats = 8'd16;
        endcase
    end

    // ============================================================
    // Handshake logic
    // ============================================================

    assign nvdla_bdma_inp_data_prdy =
        nvdla_bdma_out_data_prdy | ~nvdla_bdma_out_data_pvld;

    wire fire = nvdla_bdma_inp_data_pvld & nvdla_bdma_inp_data_prdy & nvdla_bdma_reg2zd_cfg_enable;

    // ============================================================
    // Data pipeline
    // ============================================================

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_data_pvld <= 1'b0;
        else if (nvdla_bdma_inp_data_prdy)
            nvdla_bdma_out_data_pvld <= nvdla_bdma_inp_data_pvld & nvdla_bdma_reg2zd_cfg_enable;
    end

    always @(posedge nvdla_core_clk) begin
        if (fire)
            nvdla_bdma_out_data_pd <= nvdla_bdma_inp_data_pd;
    end

    // ============================================================
    // Beat counter
    // ============================================================

    reg [7:0] beat_cnt;

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            beat_cnt <= 0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            beat_cnt <= 0;
        else if (fire) begin
            if (beat_cnt == block_beats - 1)
                beat_cnt <= 0;
            else
                beat_cnt <= beat_cnt + 1'b1;
        end
    end

    wire block_done = fire && (beat_cnt == block_beats - 1);

    // ============================================================
    // Zero accumulation (correct timing)
    // ============================================================

    wire data_is_zero = ~(|nvdla_bdma_inp_data_pd);
    reg  any_nonzero;

    wire next_any_nonzero = any_nonzero | ~data_is_zero;

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            any_nonzero <= 1'b0;
        else if (!nvdla_bdma_reg2zd_cfg_enable)
            any_nonzero <= 1'b0;
        else if (fire) begin
            if (block_done)
                any_nonzero <= 1'b0;
            else
                any_nonzero <= next_any_nonzero;
        end
    end

    // ============================================================
    // Block result generation (cycle-exact)
    // ============================================================

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
        else if (block_done)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
        else if (nvdla_bdma_out_blk_is_zero_vld &&
                 nvdla_bdma_out_blk_is_zero_rdy)
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
    end

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_blk_is_zero <= 1'b0;
        else if (block_done)
            nvdla_bdma_out_blk_is_zero <= ~next_any_nonzero;
    end

    // ============================================================
    // Overflow — should NEVER happen (per spec)
    // ============================================================

    assign nvdla_bdma_zd2reg_error_overflow = 1'b0;

endmodule
