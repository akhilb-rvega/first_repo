`timescale 1ns/1ps

module NV_NVDLA_BDMA_zero_detector (
    input  wire         nvdla_core_clk,
    input  wire         nvdla_core_rstn,

    input  wire [1:0]   nvdla_bdma_reg2zd_cfg_block_size,
    input  wire         nvdla_bdma_reg2zd_cfg_enable,

    output reg          nvdla_bdma_zd2reg_error_overflow,

    input  wire [511:0] nvdla_bdma_inp_data_pd,
    input  wire         nvdla_bdma_inp_data_pvld,
    output wire         nvdla_bdma_inp_data_prdy,

    output reg  [511:0] nvdla_bdma_out_data_pd,
    output reg          nvdla_bdma_out_data_pvld,
    input  wire         nvdla_bdma_out_data_prdy,

    output reg          nvdla_bdma_out_blk_is_zero,
    output reg          nvdla_bdma_out_blk_is_zero_vld,
    input  wire         nvdla_bdma_out_blk_is_zero_rdy
);

    // ------------------------------------------------------------
    // Beats per block (512b = 64B per beat)
    // ------------------------------------------------------------
    reg [1:0] block_beats;

    always @(*) begin
        case (nvdla_bdma_reg2zd_cfg_block_size)
            2'd0: block_beats = 2'd1; // 16B
            2'd1: block_beats = 2'd1; // 32B
            2'd2: block_beats = 2'd1; // 64B
            2'd3: block_beats = 2'd2; // 128B
            default: block_beats = 2'd1;
        endcase
    end

    // ------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------
    reg [1:0] beat_cnt;
    reg       any_nonzero;

    wire accept_inp =
        nvdla_bdma_reg2zd_cfg_enable &&
        nvdla_bdma_inp_data_pvld &&
        nvdla_bdma_inp_data_prdy;

    wire last_beat = (beat_cnt == block_beats - 1'b1);

    // ------------------------------------------------------------
    // Input ready
    // ------------------------------------------------------------
    assign nvdla_bdma_inp_data_prdy =
        !nvdla_bdma_out_data_pvld || nvdla_bdma_out_data_prdy;

    // ------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            beat_cnt                       <= 0;
            any_nonzero                    <= 1'b0;
            nvdla_bdma_out_data_pvld        <= 1'b0;
            nvdla_bdma_out_blk_is_zero_vld  <= 1'b0;
            nvdla_bdma_out_blk_is_zero      <= 1'b0;
            nvdla_bdma_zd2reg_error_overflow<= 1'b0;
        end else begin

            // --------------------------------------------
            // Disable → clean reset
            // --------------------------------------------
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                beat_cnt                      <= 0;
                any_nonzero                   <= 1'b0;
                nvdla_bdma_out_blk_is_zero_vld<= 1'b0;
            end

            // --------------------------------------------
            // Input accept
            // --------------------------------------------
            if (accept_inp) begin
                nvdla_bdma_out_data_pd   <= nvdla_bdma_inp_data_pd;
                nvdla_bdma_out_data_pvld <= 1'b1;

                if (|nvdla_bdma_inp_data_pd)
                    any_nonzero <= 1'b1;

                if (last_beat) begin
                    nvdla_bdma_out_blk_is_zero     <= ~(any_nonzero | |nvdla_bdma_inp_data_pd);
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
                    beat_cnt                       <= 0;
                    any_nonzero                    <= 1'b0;
                end else begin
                    beat_cnt <= beat_cnt + 1'b1;
                end
            end

            // --------------------------------------------
            // Output data handshake
            // --------------------------------------------
            if (nvdla_bdma_out_data_pvld &&
                nvdla_bdma_out_data_prdy) begin
                nvdla_bdma_out_data_pvld <= 1'b0;
            end

            // --------------------------------------------
            // Block result handshake
            // --------------------------------------------
            if (nvdla_bdma_out_blk_is_zero_vld &&
                nvdla_bdma_out_blk_is_zero_rdy) begin
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            end
        end
    end

endmodule
