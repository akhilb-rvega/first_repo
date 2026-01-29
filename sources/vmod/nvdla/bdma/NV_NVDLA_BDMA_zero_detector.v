`timescale 1ns/1ns
module zero_detector #(
    parameter int DATA_WIDTH   = 256,
    parameter int BLOCK_BEATS  = 16,
    parameter int CNT_WIDTH    = $clog2(BLOCK_BEATS + 1)
)(
    input  logic                      clk,
    input  logic                      rst_n,

    // ------------------------------------------------------------
    // Configuration
    // ------------------------------------------------------------
    input  logic                      nvdla_bdma_cfg_enable,
    input  logic                      nvdla_bdma_cfg_bypass,

    // ------------------------------------------------------------
    // Input Stream Interface
    // ------------------------------------------------------------
    input  logic                      nvdla_bdma_in_valid,
    output logic                      nvdla_bdma_in_ready,
    input  logic [DATA_WIDTH-1:0]     nvdla_bdma_in_data,
    input  logic                      nvdla_bdma_in_last,

    // ------------------------------------------------------------
    // Output Stream Interface
    // ------------------------------------------------------------
    output logic                      nvdla_bdma_out_valid,
    input  logic                      nvdla_bdma_out_ready,
    output logic [DATA_WIDTH-1:0]     nvdla_bdma_out_data,
    output logic                      nvdla_bdma_out_blk_last,
    output logic                      nvdla_bdma_out_blk_is_zero,

    // ------------------------------------------------------------
    // Status
    // ------------------------------------------------------------
    output logic                      nvdla_bdma_err_overflow
);

    // ============================================================
    // FSM States
    // ============================================================

    typedef enum logic [1:0] {
        ST_IDLE  = 2'b00,
        ST_RUN   = 2'b01,
        ST_FLUSH = 2'b10,
        ST_ERR   = 2'b11
    } state_t;

    state_t state, state_n;

    // ============================================================
    // Internal Registers
    // ============================================================

    logic [CNT_WIDTH-1:0]  beat_cnt;
    logic                  any_nonzero;
    logic                  block_done;
    logic                  overflow;

    // ============================================================
    // Zero Detection Logic
    // ============================================================

    logic data_is_zero;

    assign data_is_zero = (nvdla_bdma_in_data == {DATA_WIDTH{1'b0}});

    // ============================================================
    // Handshake
    // ============================================================

    assign nvdla_bdma_in_ready = nvdla_bdma_out_ready | ~nvdla_bdma_out_valid;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            nvdla_bdma_out_valid <= 1'b0;
        else if (nvdla_bdma_in_ready)
            nvdla_bdma_out_valid <= nvdla_bdma_in_valid;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            nvdla_bdma_out_data <= '0;
        else if (nvdla_bdma_in_ready && nvdla_bdma_in_valid)
            nvdla_bdma_out_data <= nvdla_bdma_in_data;
    end

    // ============================================================
    // FSM State Register
    // ============================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= ST_IDLE;
        else
            state <= state_n;
    end

    // ============================================================
    // FSM Next-State Logic
    // ============================================================

    always_comb begin
        state_n = state;

        case (state)
            ST_IDLE: begin
                if (nvdla_bdma_cfg_enable && nvdla_bdma_in_valid && nvdla_bdma_in_ready)
                    state_n = ST_RUN;
            end

            ST_RUN: begin
                if (block_done)
                    state_n = ST_FLUSH;
                else if (overflow)
                    state_n = ST_ERR;
            end

            ST_FLUSH: begin
                if (nvdla_bdma_in_valid && nvdla_bdma_in_ready)
                    state_n = ST_RUN;
                else
                    state_n = ST_IDLE;
            end

            ST_ERR: begin
                if (!nvdla_bdma_cfg_enable)
                    state_n = ST_IDLE;
            end

            default:
                state_n = ST_IDLE;
        endcase
    end

    // ============================================================
    // Beat Counter + Block Boundary Logic
    // ============================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            beat_cnt <= '0;
        else if (state == ST_IDLE)
            beat_cnt <= '0;
        else if (nvdla_bdma_in_valid && nvdla_bdma_in_ready) begin
            if (block_done)
                beat_cnt <= '0;
            else
                beat_cnt <= beat_cnt + 1'b1;
        end
    end

    assign block_done = (nvdla_bdma_in_valid && nvdla_bdma_in_ready) &&
                        ((beat_cnt == BLOCK_BEATS-1) || nvdla_bdma_in_last);

    // ============================================================
    // Non-zero Accumulation
    // ============================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            any_nonzero <= 1'b0;
        else if (state == ST_IDLE)
            any_nonzero <= 1'b0;
        else if (nvdla_bdma_in_valid && nvdla_bdma_in_ready) begin
            if (block_done)
                any_nonzero <= 1'b0;
            else if (!data_is_zero)
                any_nonzero <= 1'b1;
        end
    end

    // ============================================================
    // Overflow Protection
    // ============================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            overflow <= 1'b0;
        else if (state == ST_IDLE)
            overflow <= 1'b0;
        else if ((beat_cnt == BLOCK_BEATS) && nvdla_bdma_in_valid && nvdla_bdma_in_ready)
            overflow <= 1'b1;
    end

    assign nvdla_bdma_err_overflow = overflow;

    // ============================================================
    // Output Block Metadata
    // ============================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            nvdla_bdma_out_blk_last    <= 1'b0;
            nvdla_bdma_out_blk_is_zero <= 1'b0;
        end else if (nvdla_bdma_in_ready) begin
            nvdla_bdma_out_blk_last <= block_done;

            if (block_done) begin
                if (nvdla_bdma_cfg_bypass || !nvdla_bdma_cfg_enable)
                    nvdla_bdma_out_blk_is_zero <= 1'b0;
                else
                    nvdla_bdma_out_blk_is_zero <= ~any_nonzero & data_is_zero;
            end else begin
                nvdla_bdma_out_blk_is_zero <= 1'b0;
            end
        end
    end

endmodule
