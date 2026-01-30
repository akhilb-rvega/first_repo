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
    // Constants
    // ============================================================

    localparam ST_IDLE  = 2'd0;
    localparam ST_RUN   = 2'd1;
    localparam ST_FLUSH = 2'd2;
    localparam ST_ERR   = 2'd3;

    // ============================================================
    // Registers
    // ============================================================

    reg [1:0]  state, state_n;
    reg [7:0]  beat_cnt;
    reg        any_nonzero;
    reg        overflow;
    reg [7:0]  block_beats;

    wire       data_is_zero;
    wire       block_done;
    wire       next_any_nonzero;

    // ============================================================
    // Block Size Decode
    // ============================================================

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
    // Zero Detection
    // ============================================================

    assign data_is_zero = ~(|nvdla_bdma_inp_data_pd);

    // ============================================================
    // Handshake
    // ============================================================

    assign nvdla_bdma_inp_data_prdy =
        nvdla_bdma_out_data_prdy | ~nvdla_bdma_out_data_pvld;

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            nvdla_bdma_out_data_pvld <= 1'b0;
        else if (nvdla_bdma_inp_data_prdy)
            nvdla_bdma_out_data_pvld <= nvdla_bdma_inp_data_pvld;
    end

    always @(posedge nvdla_core_clk) begin
        if (nvdla_bdma_inp_data_pvld && nvdla_bdma_inp_data_prdy)
            nvdla_bdma_out_data_pd <= nvdla_bdma_inp_data_pd;
    end

    // ============================================================
    // FSM Register
    // ============================================================

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            state <= ST_IDLE;
        else
            state <= state_n;
    end

    // ============================================================
    // FSM Next State
    // ============================================================

    always @(*) begin
        state_n = state;
        case (state)
            ST_IDLE:
                if (nvdla_bdma_reg2zd_cfg_enable &&
                    nvdla_bdma_inp_data_pvld &&
                    nvdla_bdma_inp_data_prdy)
                    state_n = ST_RUN;

            ST_RUN:
                if (block_done)
                    state_n = ST_FLUSH;
                else if (overflow)
                    state_n = ST_ERR;

            ST_FLUSH:
                if (nvdla_bdma_inp_data_pvld &&
                    nvdla_bdma_inp_data_prdy)
                    state_n = ST_RUN;
                else
                    state_n = ST_IDLE;

            ST_ERR:
                if (!nvdla_bdma_reg2zd_cfg_enable)
                    state_n = ST_IDLE;
        endcase
    end

    // ============================================================
    // Beat Counter
    // ============================================================

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            beat_cnt <= 0;
        else if (state == ST_IDLE)
            beat_cnt <= 0;
        else if (nvdla_bdma_inp_data_pvld &&
                 nvdla_bdma_inp_data_prdy) begin
            if (block_done)
                beat_cnt <= 0;
            else
                beat_cnt <= beat_cnt + 1'b1;
        end
    end

    assign block_done =
        (nvdla_bdma_inp_data_pvld &&
         nvdla_bdma_inp_data_prdy &&
         (beat_cnt == block_beats - 1));

    // ============================================================
    // Non-zero Accumulation (FIXED)
    // ============================================================

    assign next_any_nonzero = any_nonzero | (~data_is_zero);

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            any_nonzero <= 1'b0;
        else if (state == ST_IDLE)
            any_nonzero <= 1'b0;
        else if (nvdla_bdma_inp_data_pvld &&
                 nvdla_bdma_inp_data_prdy) begin
            if (block_done)
                any_nonzero <= 1'b0;
            else
                any_nonzero <= next_any_nonzero;
        end
    end

    // ============================================================
    // Overflow Detection
    // ============================================================

    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn)
            overflow <= 1'b0;
        else if (state == ST_IDLE)
            overflow <= 1'b0;
        else if ((beat_cnt == block_beats) &&
                 nvdla_bdma_inp_data_pvld &&
                 nvdla_bdma_inp_data_prdy)
            overflow <= 1'b1;
    end

    assign nvdla_bdma_zd2reg_error_overflow = overflow;

    // ============================================================
    // Output Block Result (FIXED TIMING)
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

endmodule
