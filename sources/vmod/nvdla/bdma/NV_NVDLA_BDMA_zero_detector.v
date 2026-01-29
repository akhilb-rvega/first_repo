`timescale 1ns/1ps

module NV_NVDLA_BDMA_zero_detector (
    input  wire         nvdla_core_clk,
    input  wire         nvdla_core_rstn,

    input  wire [1:0]   nvdla_bdma_reg2zd_cfg_block_size,
    input  wire         nvdla_bdma_reg2zd_cfg_enable,

    output wire         nvdla_bdma_zd2reg_error_overflow,

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

    assign nvdla_bdma_zd2reg_error_overflow = 1'b0;

    // ------------------------------------------------------------
    // Block size decode
    // ------------------------------------------------------------
    function [7:0] decode_beats(input [1:0] cfg);
        case (cfg)
            2'd0: decode_beats = 8'd16;
            2'd1: decode_beats = 8'd32;
            2'd2: decode_beats = 8'd64;
            2'd3: decode_beats = 8'd128;
            default: decode_beats = 8'd16;
        endcase
    endfunction

    // ------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------
    reg [7:0] beat_cnt;
    reg [7:0] block_beats;
    reg       any_nonzero;
    reg       in_block;

    // ------------------------------------------------------------
    // Flow control
    // ------------------------------------------------------------
    wire allow_new_block;
    wire in_fire;
    wire out_fire;

    assign allow_new_block =
        !nvdla_bdma_out_blk_is_zero_vld ||
         nvdla_bdma_out_blk_is_zero_rdy;

    assign nvdla_bdma_inp_data_prdy =
        nvdla_bdma_reg2zd_cfg_enable &&
        allow_new_block &&
        (!nvdla_bdma_out_data_pvld || nvdla_bdma_out_data_prdy);

    assign in_fire  = nvdla_bdma_inp_data_pvld && nvdla_bdma_inp_data_prdy;
    assign out_fire = nvdla_bdma_out_data_pvld && nvdla_bdma_out_data_prdy;

    // ------------------------------------------------------------
    // Sequential
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            nvdla_bdma_out_data_pvld       <= 1'b0;
            nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            nvdla_bdma_out_blk_is_zero     <= 1'b0;
            beat_cnt                       <= 8'd0;
            block_beats                   <= 8'd16;
            any_nonzero                    <= 1'b0;
            in_block                       <= 1'b0;
        end else begin

            // -------------------------------
            // Disable → hard abort
            // -------------------------------
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                nvdla_bdma_out_data_pvld       <= 1'b0;
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
                beat_cnt                       <= 8'd0;
                any_nonzero                    <= 1'b0;
                in_block                       <= 1'b0;
            end else begin

                // -------------------------------
                // Accept input
                // -------------------------------
                if (in_fire) begin
                    nvdla_bdma_out_data_pd   <= nvdla_bdma_inp_data_pd;
                    nvdla_bdma_out_data_pvld <= 1'b1;

                    if (!in_block) begin
                        block_beats <= decode_beats(nvdla_bdma_reg2zd_cfg_block_size);
                        in_block    <= 1'b1;
                        beat_cnt    <= 8'd1;
                        any_nonzero <= |nvdla_bdma_inp_data_pd;
                    end else begin
                        beat_cnt    <= beat_cnt + 1'b1;
                        any_nonzero <= any_nonzero | (|nvdla_bdma_inp_data_pd);
                    end
                end

                // -------------------------------
                // Output handshake
                // -------------------------------
                if (out_fire) begin
                    nvdla_bdma_out_data_pvld <= 1'b0;

                    if (in_block && (beat_cnt == block_beats)) begin
                        nvdla_bdma_out_blk_is_zero     <= ~any_nonzero;
                        nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
                        beat_cnt                       <= 8'd0;
                        any_nonzero                    <= 1'b0;
                        in_block                       <= 1'b0;
                    end
                end

                // -------------------------------
                // Result handshake
                // -------------------------------
                if (nvdla_bdma_out_blk_is_zero_vld &&
                    nvdla_bdma_out_blk_is_zero_rdy) begin
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
                end
            end
        end
    end

endmodule
