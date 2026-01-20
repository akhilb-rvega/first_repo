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

    // ------------------------------------------------------------
    // FSM
    // ------------------------------------------------------------
    localparam ST_IDLE  = 1'b0;
    localparam ST_DONE  = 1'b1;

    reg state, next_state;

    // ------------------------------------------------------------
    // Data register
    // ------------------------------------------------------------
    reg [7:0] data_pd_r;
    reg       data_pvld_r;

    // ------------------------------------------------------------
    // Handshake
    // ------------------------------------------------------------
    wire in_accept;
    wire out_accept;

    assign in_accept  = nvdla_bdma_inp_data_pvld &
                        nvdla_bdma_inp_data_prdy;

    assign out_accept = nvdla_bdma_out_data_pvld &
                        nvdla_bdma_out_data_prdy;

    // ------------------------------------------------------------
    // Ready logic - with buffering in both modes
    // ------------------------------------------------------------
    assign nvdla_bdma_inp_data_prdy = (!data_pvld_r || nvdla_bdma_out_data_prdy);

    // ------------------------------------------------------------
    // Output datapath - always use buffered path
    // ------------------------------------------------------------
    assign nvdla_bdma_out_data_pd = data_pd_r;
    assign nvdla_bdma_out_data_pvld = data_pvld_r;

    // ------------------------------------------------------------
    // FSM next-state
    // ------------------------------------------------------------
    always @(*) begin
        next_state = state;
        case (state)
            ST_IDLE: begin
                if (nvdla_bdma_reg2zd_cfg_enable && in_accept)
                    next_state = ST_DONE;
            end

            ST_DONE: begin
                if (nvdla_bdma_out_blk_is_zero_vld &&
                    nvdla_bdma_out_blk_is_zero_rdy)
                    next_state = ST_IDLE;
            end

            default: next_state = ST_IDLE;
        endcase
    end

    // ------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            state                             <= ST_IDLE;
            data_pd_r                         <= 8'd0;
            data_pvld_r                       <= 1'b0;
            nvdla_bdma_out_blk_is_zero         <= 1'b1;
            nvdla_bdma_out_blk_is_zero_vld     <= 1'b0;
            nvdla_bdma_zd2reg_error_overflow   <= 1'b0;
        end else begin
            state <= next_state;

            // Error permanently disabled
            nvdla_bdma_zd2reg_error_overflow <= 1'b0;

            // Data register - always buffer data for both bypass and enabled modes
            if (in_accept) begin
                data_pd_r   <= nvdla_bdma_inp_data_pd;
                data_pvld_r <= 1'b1;
            end else if (out_accept) begin
                data_pvld_r <= 1'b0;
            end

            // Zero detection and metadata - only when enabled
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            end else begin
                if (in_accept) begin
                    nvdla_bdma_out_blk_is_zero     <= (nvdla_bdma_inp_data_pd == 8'd0);
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
                end else if (nvdla_bdma_out_blk_is_zero_vld &&
                             nvdla_bdma_out_blk_is_zero_rdy) begin
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
                end
            end
        end
    end

endmodule
