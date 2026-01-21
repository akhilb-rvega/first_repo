// ================================================================
// NV_NVDLA_BDMA_zero_detector
// 8-bit per-beat zero detector (spec-compliant, hardened)
// ================================================================
`timescale 1ns/1ns

module NV_NVDLA_BDMA_zero_detector (
    input  wire        nvdla_core_clk,
    input  wire        nvdla_core_rstn,

    // Configuration
    input  wire [1:0]  nvdla_bdma_reg2zd_cfg_block_size, // reserved
    input  wire        nvdla_bdma_reg2zd_cfg_enable,

    // Error reporting (unused)
    output wire        nvdla_bdma_zd2reg_error_overflow,

    // Input stream
    input  wire [7:0]  nvdla_bdma_inp_data_pd,
    input  wire        nvdla_bdma_inp_data_pvld,
    output wire        nvdla_bdma_inp_data_prdy,

    // Output stream
    output wire [7:0]  nvdla_bdma_out_data_pd,
    output wire        nvdla_bdma_out_data_pvld,
    input  wire        nvdla_bdma_out_data_prdy,

    // Zero detection metadata (per beat)
    output reg         nvdla_bdma_out_blk_is_zero,
    output reg         nvdla_bdma_out_blk_is_zero_vld,
    input  wire        nvdla_bdma_out_blk_is_zero_rdy
);

    // ------------------------------------------------------------
    // Error permanently disabled
    // ------------------------------------------------------------
    assign nvdla_bdma_zd2reg_error_overflow = 1'b0;

    // ------------------------------------------------------------
    // FSM for metadata lifetime
    // ------------------------------------------------------------
    localparam ST_IDLE = 1'b0;
    localparam ST_DONE = 1'b1;

    reg state, state_n;

    // ------------------------------------------------------------
    // Single-beat storage
    // ------------------------------------------------------------
    reg [7:0] data_r;
    reg       data_vld_r;

    reg       zero_r;
    reg       zero_vld_r;

    // ------------------------------------------------------------
    // Handshakes
    // ------------------------------------------------------------
    wire in_accept;
    wire out_accept;
    wire meta_accept;

    assign in_accept =
        nvdla_bdma_inp_data_pvld & nvdla_bdma_inp_data_prdy;

    assign out_accept =
        nvdla_bdma_out_data_pvld & nvdla_bdma_out_data_prdy;

    assign meta_accept =
        nvdla_bdma_out_blk_is_zero_vld &
        nvdla_bdma_out_blk_is_zero_rdy;

    // ------------------------------------------------------------
    // READY LOGIC (CRITICAL FIX)
    // - Stall input if *either* data OR metadata is pending
    // ------------------------------------------------------------
    assign nvdla_bdma_inp_data_prdy =
        !nvdla_bdma_reg2zd_cfg_enable
            ? nvdla_bdma_out_data_prdy
            : (!data_vld_r && !zero_vld_r);

    // ------------------------------------------------------------
    // Output datapath
    // ------------------------------------------------------------
    assign nvdla_bdma_out_data_pd =
        nvdla_bdma_reg2zd_cfg_enable ? data_r :
                                      nvdla_bdma_inp_data_pd;

    assign nvdla_bdma_out_data_pvld =
        nvdla_bdma_reg2zd_cfg_enable ? data_vld_r :
                                      nvdla_bdma_inp_data_pvld;

    // ------------------------------------------------------------
    // FSM next-state logic
    // ------------------------------------------------------------
    always @(*) begin
        state_n = state;
        case (state)
            ST_IDLE: begin
                if (nvdla_bdma_reg2zd_cfg_enable && in_accept)
                    state_n = ST_DONE;
            end
            ST_DONE: begin
                if (meta_accept)
                    state_n = ST_IDLE;
            end
        endcase
    end

    // ------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            state                          <= ST_IDLE;
            data_r                         <= 8'd0;
            data_vld_r                     <= 1'b0;
            zero_r                         <= 1'b1;
            zero_vld_r                     <= 1'b0;
            nvdla_bdma_out_blk_is_zero     <= 1'b1;
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
        end else begin
            state <= state_n;

            // ----------------------------------------------------
            // Disable behavior
            // - Allow in-flight DATA to drain
            // - Suppress all METADATA
            // ----------------------------------------------------
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                zero_vld_r                     <= 1'b0;
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;

                if (out_accept)
                    data_vld_r <= 1'b0;
            end else begin
                // -----------------------------------------------
                // Input accept
                // -----------------------------------------------
                if (in_accept) begin
                    data_r     <= nvdla_bdma_inp_data_pd;
                    data_vld_r <= 1'b1;
                    zero_r     <= (nvdla_bdma_inp_data_pd == 8'd0);
                    zero_vld_r <= 1'b1;
                end

                // -----------------------------------------------
                // Data output handshake
                // -----------------------------------------------
                if (out_accept)
                    data_vld_r <= 1'b0;

                // -----------------------------------------------
                // Metadata output handshake
                // -----------------------------------------------
                if (state == ST_DONE && zero_vld_r) begin
                    nvdla_bdma_out_blk_is_zero     <= zero_r;
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
                end

                if (meta_accept) begin
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
                    zero_vld_r                     <= 1'b0;
                end
            end
        end
    end

endmodule
