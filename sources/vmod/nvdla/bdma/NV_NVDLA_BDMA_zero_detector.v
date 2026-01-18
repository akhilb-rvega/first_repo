// ================================================================
//  NV_NVDLA_BDMA_zero_detector - 512-bit Block-Level Zero Detector
// ================================================================
`timescale 1ns / 1ps

module NV_NVDLA_BDMA_zero_detector (
   nvdla_core_clk                //|< i
  ,nvdla_core_rstn               //|< i
  ,nvdla_bdma_reg2zd_cfg_block_size         //|< i  // Block size in beats (0=16, 1=32, 2=64, 3=128)
  ,nvdla_bdma_reg2zd_cfg_enable             //|< i  // Enable zero detection (1) or bypass (0)
  ,nvdla_bdma_zd2reg_error_overflow         //|> o  // Error: beat count overflow detected
  ,nvdla_bdma_inp_data_pd                   //|< i  // Input data packet [511:0]
  ,nvdla_bdma_inp_data_pvld                 //|< i  // Input data valid
  ,nvdla_bdma_inp_data_prdy                 //|> o  // Input data ready
  ,nvdla_bdma_out_data_pd                   //|> o  // Output data packet [511:0] (pass-through)
  ,nvdla_bdma_out_data_pvld                 //|> o  // Output data valid
  ,nvdla_bdma_out_data_prdy                 //|< i  // Output data ready
  ,nvdla_bdma_out_blk_is_zero               //|> o  // Block-level zero detection result
  ,nvdla_bdma_out_blk_is_zero_vld           //|> o  // Block result valid (asserted at block boundary)
  ,nvdla_bdma_out_blk_is_zero_rdy           //|< i  // Block result ready
  );

//
// NV_NVDLA_BDMA_zero_detector_ports.v
//
input  nvdla_core_clk;   /* inp_data, out_data, out_blk_is_zero */
input  nvdla_core_rstn;  /* inp_data, out_data, out_blk_is_zero */

// Configuration
input  [1:0] nvdla_bdma_reg2zd_cfg_block_size;  // 0=16, 1=32, 2=64, 3=128 beats per block
input        nvdla_bdma_reg2zd_cfg_enable;      // 1=enabled, 0=bypass mode

// Error reporting
output reg   nvdla_bdma_zd2reg_error_overflow;

// Input data stream
input  [511:0] nvdla_bdma_inp_data_pd;          // 512-bit data word
input          nvdla_bdma_inp_data_pvld;        // Input valid
output         nvdla_bdma_inp_data_prdy;         // Input ready

// Output data stream (pass-through)
output [511:0] nvdla_bdma_out_data_pd;          // 512-bit data word
output         nvdla_bdma_out_data_pvld;        // Output valid
input          nvdla_bdma_out_data_prdy;         // Output ready

// Block-level zero detection result
output reg     nvdla_bdma_out_blk_is_zero;      // 1=all zeros, 0=has non-zero
output reg     nvdla_bdma_out_blk_is_zero_vld;  // Result valid (at block boundary)
input          nvdla_bdma_out_blk_is_zero_rdy;  // Result ready

// ============================================================
// FSM States
// ============================================================
localparam ST_IDLE         = 2'd0;
localparam ST_DETECTING    = 2'd1;
localparam ST_BLOCK_DONE   = 2'd2;
localparam ST_ERROR        = 2'd3;

reg [1:0] state, next_state;

// ============================================================
// Beat Counter
// ============================================================
reg [7:0] beat_count;
wire [7:0] block_size_beats;

// Block size decoding
assign block_size_beats = (nvdla_bdma_reg2zd_cfg_block_size == 2'd0) ? 8'd16  :
                          (nvdla_bdma_reg2zd_cfg_block_size == 2'd1) ? 8'd32  :
                          (nvdla_bdma_reg2zd_cfg_block_size == 2'd2) ? 8'd64  :
                                                                       8'd128 ;

// ============================================================
// Data Path Registers
// ============================================================
reg [511:0] data_pd_r;
reg         data_pvld_r;

// ============================================================
// Zero Detection Logic
// ============================================================
reg block_is_zero_r;  // Accumulator: 1 if all beats so far are zero

wire current_beat_is_zero;
assign current_beat_is_zero = (nvdla_bdma_inp_data_pd == 512'd0);

// ============================================================
// Handshake Signals
// ============================================================
wire in_accept, out_accept, blk_result_accept;

assign in_accept         = nvdla_bdma_inp_data_pvld & nvdla_bdma_inp_data_prdy;
assign out_accept        = nvdla_bdma_out_data_pvld & nvdla_bdma_out_data_prdy;
assign blk_result_accept = nvdla_bdma_out_blk_is_zero_vld & nvdla_bdma_out_blk_is_zero_rdy;

// ============================================================
// Data Path Ready Logic
// ============================================================
wire data_path_ready;

assign data_path_ready = (state == ST_IDLE) || 
                         (state == ST_DETECTING) ||
                         (state == ST_BLOCK_DONE && blk_result_accept);

assign nvdla_bdma_inp_data_prdy = nvdla_bdma_reg2zd_cfg_enable ? 
                                  (data_path_ready && (!data_pvld_r || nvdla_bdma_out_data_prdy)) :
                                  nvdla_bdma_out_data_prdy;  // Bypass mode

// ============================================================
// Data Path Output
// ============================================================
assign nvdla_bdma_out_data_pd = nvdla_bdma_reg2zd_cfg_enable ? 
                                data_pd_r : 
                                nvdla_bdma_inp_data_pd;  // Bypass

assign nvdla_bdma_out_data_pvld = nvdla_bdma_reg2zd_cfg_enable ? 
                                  data_pvld_r : 
                                  nvdla_bdma_inp_data_pvld;  // Bypass

// ============================================================
// FSM Next State Logic
// ============================================================
always @(*) begin
    next_state = state;
    case (state)
        ST_IDLE: begin
            if (nvdla_bdma_reg2zd_cfg_enable && in_accept)
                next_state = (beat_count == block_size_beats - 1) ? ST_BLOCK_DONE : ST_DETECTING;
        end

        ST_DETECTING: begin
            if (in_accept) begin
                if (beat_count >= block_size_beats)
                    next_state = ST_ERROR;  // Overflow
                else if (beat_count == block_size_beats - 1)
                    next_state = ST_BLOCK_DONE;
            end
        end

        ST_BLOCK_DONE: begin
            if (blk_result_accept)
                next_state = ST_IDLE;
        end

        ST_ERROR: begin
            // Stay in error until disabled
            if (!nvdla_bdma_reg2zd_cfg_enable)
                next_state = ST_IDLE;
        end

        default: next_state = ST_IDLE;
    endcase
end

// ============================================================
// Sequential Logic
// ============================================================
always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
    if (!nvdla_core_rstn) begin
        state                             <= ST_IDLE;
        beat_count                        <= 8'd0;
        block_is_zero_r                   <= 1'b1;
        data_pd_r                         <= 512'd0;
        data_pvld_r                       <= 1'b0;
        nvdla_bdma_out_blk_is_zero        <= 1'b0;
        nvdla_bdma_out_blk_is_zero_vld    <= 1'b0;
        nvdla_bdma_zd2reg_error_overflow  <= 1'b0;
    end else begin
        state <= next_state;

        // Disable clears state
        if (!nvdla_bdma_reg2zd_cfg_enable) begin
            beat_count                        <= 8'd0;
            block_is_zero_r                   <= 1'b1;
            data_pvld_r                       <= 1'b0;
            nvdla_bdma_out_blk_is_zero_vld    <= 1'b0;
            nvdla_bdma_zd2reg_error_overflow  <= 1'b0;
        end else begin
            // Data register
            if (in_accept) begin
                data_pd_r   <= nvdla_bdma_inp_data_pd;
                data_pvld_r <= 1'b1;
            end else if (out_accept) begin
                data_pvld_r <= 1'b0;
            end

            // Beat counter and zero accumulation
            case (state)
                ST_IDLE: begin
                    if (in_accept) begin
                        beat_count      <= 8'd1;
                        block_is_zero_r <= current_beat_is_zero;
                    end else begin
                        beat_count      <= 8'd0;
                        block_is_zero_r <= 1'b1;
                    end
                end

                ST_DETECTING: begin
                    if (in_accept) begin
                        beat_count      <= beat_count + 1;
                        block_is_zero_r <= block_is_zero_r & current_beat_is_zero;
                    end
                end

                ST_BLOCK_DONE: begin
                    if (blk_result_accept) begin
                        beat_count      <= 8'd0;
                        block_is_zero_r <= 1'b1;
                    end
                end

                ST_ERROR: begin
                    // Hold error state
                end
            endcase

            // Block result output
            if (next_state == ST_BLOCK_DONE && state != ST_BLOCK_DONE) begin
                nvdla_bdma_out_blk_is_zero     <= block_is_zero_r & current_beat_is_zero;
                nvdla_bdma_out_blk_is_zero_vld <= 1'b1;
            end else if (blk_result_accept) begin
                nvdla_bdma_out_blk_is_zero_vld <= 1'b0;
            end

            // Error overflow
            if (state == ST_ERROR)
                nvdla_bdma_zd2reg_error_overflow <= 1'b1;
            else
                nvdla_bdma_zd2reg_error_overflow <= 1'b0;
        end
    end
end

endmodule // NV_NVDLA_BDMA_zero_detector
