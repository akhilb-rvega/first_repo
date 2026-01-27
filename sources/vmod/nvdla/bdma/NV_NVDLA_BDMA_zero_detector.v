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
    // Block size decode
    // ------------------------------------------------------------
    reg [7:0] block_beats;
    always @(*) begin
        case (nvdla_bdma_reg2zd_cfg_block_size)
            2'd0: block_beats = 8'd16;
            2'd1: block_beats = 8'd32;
            2'd2: block_beats = 8'd64;
            2'd3: block_beats = 8'd128;
        endcase
    end

    // ------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------
    reg [7:0] beat_cnt;
    reg       any_nonzero;

    wire out_accept =
        nvdla_bdma_out_data_pvld &&
        nvdla_bdma_out_data_prdy;

    // Input can be accepted only when enabled AND
    // buffer is empty or output is being accepted
    assign nvdla_bdma_inp_data_prdy =
        nvdla_bdma_reg2zd_cfg_enable &&
        (!nvdla_bdma_out_data_pvld || out_accept);

    wire in_accept =
        nvdla_bdma_inp_data_pvld &&
        nvdla_bdma_inp_data_prdy;

    // ------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            nvdla_bdma_out_data_pvld        <= 1'b0;
            nvdla_bdma_out_blk_is_zero_vld  <= 1'b0;
            nvdla_bdma_out_blk_is_zero      <= 1'b1;
            beat_cnt                        <= 8'd0;
            any_nonzero                     <= 1'b0;
            nvdla_bdma_zd2reg_error_overflow<= 1'b0;
        end else begin

            // -------------------------------
            // Disable → abort block
            // -------------------------------
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                beat_cnt                       <= 8'd0;
                any_nonzero                    <= 1'b0;
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            end

            // -------------------------------
            // Output consumption
            // -------------------------------
            if (out_accept) begin
                nvdla_bdma_out_data_pvld <= 1'b0;
            end

            // -------------------------------
            // Input acceptance
            // -------------------------------
            if (in_accept) begin
                // Register data
                nvdla_bdma_out_data_pd   <= nvdla_bdma_inp_data_pd;
                nvdla_bdma_out_data_pvld <= 1'b1;

                // Accumulate zero detection
                if (|nvdla_bdma_inp_data_pd)
                    any_nonzero <= 1'b1;

                // Beat counter
                if (beat_cnt == block_beats - 1'b1) begin
                    beat_cnt <= 8'd0;
                    nvdla_bdma_out_blk_is_zero     <= ~any_nonzero & ~(|nvdla_bdma_inp_data_pd);
                    nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
                    any_nonzero                    <= 1'b0;
                end else begin
                    beat_cnt <= beat_cnt + 1'b1;
                end
            end

            // -------------------------------
            // Block result handshake
            // -------------------------------
            if (nvdla_bdma_out_blk_is_zero_vld &&
                nvdla_bdma_out_blk_is_zero_rdy) begin
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            end
        end
    end

endmodule
