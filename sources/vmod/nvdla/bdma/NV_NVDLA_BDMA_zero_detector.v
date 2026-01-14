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
output       nvdla_bdma_zd2reg_error_overflow;

// Input data stream
input  [511:0] nvdla_bdma_inp_data_pd;          // 512-bit data word
input          nvdla_bdma_inp_data_pvld;        // Input valid
output         nvdla_bdma_inp_data_prdy;         // Input ready

// Output data stream (pass-through)
output [511:0] nvdla_bdma_out_data_pd;          // 512-bit data word
output         nvdla_bdma_out_data_pvld;        // Output valid
input          nvdla_bdma_out_data_prdy;         // Output ready

// Block-level zero detection result
output         nvdla_bdma_out_blk_is_zero;      // 1=all zeros, 0=has non-zero
output         nvdla_bdma_out_blk_is_zero_vld;  // Result valid (at block boundary)
input          nvdla_bdma_out_blk_is_zero_rdy;  // Result ready

//==================================
// Internal Signals
//==================================
// FSM state
localparam ZD_STATE_IDLE         = 2'd0;
localparam ZD_STATE_DETECTING    = 2'd1;
localparam ZD_STATE_BLOCK_DONE   = 2'd2;
localparam ZD_STATE_ERROR        = 2'd3;

reg  [1:0] zd_state;
reg  [1:0] zd_state_next;

// Block size configuration (decoded)
wire [6:0] block_size_beats;  // Actual block size: 16, 32, 64, or 128

// Beat counter within current block
reg  [6:0] beat_count;
reg  [6:0] beat_count_next;

// Zero detection accumulator
reg        blk_has_nonzero;      // 1 if any non-zero word seen in current block
reg        blk_has_nonzero_next;

// Data path (pass-through)
reg  [511:0] out_data_pd_reg;
reg          out_data_pvld_reg;
wire         data_accept;         // Both input and output ready

// Block result output
reg         out_blk_is_zero_vld_reg;

// Error detection
reg         error_overflow;
reg         error_overflow_next;

//==================================
// Block Size Decoding
//==================================
assign block_size_beats = (nvdla_bdma_reg2zd_cfg_block_size == 2'd0) ? 7'd16 :
                          (nvdla_bdma_reg2zd_cfg_block_size == 2'd1) ? 7'd32 :
                          (nvdla_bdma_reg2zd_cfg_block_size == 2'd2) ? 7'd64 :
                                                            7'd128;

//==================================
// Zero Detection Logic
//==================================
// Check if 512-bit word is all zeros
wire word_is_zero;
assign word_is_zero = (nvdla_bdma_inp_data_pd == 512'd0);

//==================================
// Data Path (Pass-through)
//==================================
// In bypass mode or when enabled, pass data through with flow control
// Allow data acceptance in BLOCK_DONE state once block result is ready
wire block_done_ready_for_next;
assign block_done_ready_for_next = (zd_state == ZD_STATE_BLOCK_DONE) & nvdla_bdma_out_blk_is_zero_rdy;

wire data_path_ready;
assign data_path_ready = nvdla_bdma_reg2zd_cfg_enable ? 
                         ((zd_state != ZD_STATE_BLOCK_DONE) | block_done_ready_for_next) : 
                         1'b1;

assign data_accept = nvdla_bdma_inp_data_pvld & nvdla_bdma_out_data_prdy & data_path_ready;
assign nvdla_bdma_inp_data_prdy = nvdla_bdma_reg2zd_cfg_enable ? (data_accept & data_path_ready) : nvdla_bdma_out_data_prdy;

assign nvdla_bdma_out_data_pd = nvdla_bdma_reg2zd_cfg_enable ? out_data_pd_reg : nvdla_bdma_inp_data_pd;
assign nvdla_bdma_out_data_pvld = nvdla_bdma_reg2zd_cfg_enable ? out_data_pvld_reg : nvdla_bdma_inp_data_pvld;

//==================================
// FSM: State Machine
//==================================
always @(*) begin
    zd_state_next = zd_state;
    beat_count_next = beat_count;
    blk_has_nonzero_next = blk_has_nonzero;
    error_overflow_next = 1'b0;

    case (zd_state)
        ZD_STATE_IDLE: begin
            if (nvdla_bdma_reg2zd_cfg_enable & nvdla_bdma_inp_data_pvld & data_accept) begin
                // Start new block detection
                zd_state_next = ZD_STATE_DETECTING;
                beat_count_next = 7'd1;
                blk_has_nonzero_next = ~word_is_zero;
            end
        end

        ZD_STATE_DETECTING: begin
            if (nvdla_bdma_inp_data_pvld & data_accept) begin
                // Update zero detection
                blk_has_nonzero_next = blk_has_nonzero | (~word_is_zero);
                
                // Check if block is complete
                if (beat_count == (block_size_beats - 7'd1)) begin
                    // Block boundary reached
                    zd_state_next = ZD_STATE_BLOCK_DONE;
                    beat_count_next = 7'd0;
                end else begin
                    beat_count_next = beat_count + 7'd1;
                end
            end
        end

        ZD_STATE_BLOCK_DONE: begin
            // Wait for block result to be accepted
            if (nvdla_bdma_out_blk_is_zero_rdy) begin
                // Start next block if data available and can be accepted
                // data_accept will be true when: nvdla_bdma_inp_data_pvld & nvdla_bdma_out_data_prdy & data_path_ready
                if (data_accept) begin
                    zd_state_next = ZD_STATE_DETECTING;
                    beat_count_next = 7'd1;
                    blk_has_nonzero_next = ~word_is_zero;
                end else begin
                    zd_state_next = ZD_STATE_IDLE;
                end
            end
        end

        ZD_STATE_ERROR: begin
            // Error state - wait for reset or recovery
            if (nvdla_bdma_reg2zd_cfg_enable == 1'b0) begin
                // Disable clears error
                zd_state_next = ZD_STATE_IDLE;
            end
        end

        default: begin
            zd_state_next = ZD_STATE_IDLE;
        end
    endcase

    // Overflow detection: beat count exceeds block size
    if ((zd_state == ZD_STATE_DETECTING) && 
        (beat_count >= block_size_beats) && 
        nvdla_bdma_inp_data_pvld) begin
        error_overflow_next = 1'b1;
        zd_state_next = ZD_STATE_ERROR;
    end
end

//==================================
// State Registers
//==================================
always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
    if (!nvdla_core_rstn) begin
        zd_state <= ZD_STATE_IDLE;
        beat_count <= 7'd0;
        blk_has_nonzero <= 1'b0;
        error_overflow <= 1'b0;
    end else begin
        zd_state <= zd_state_next;
        beat_count <= beat_count_next;
        blk_has_nonzero <= blk_has_nonzero_next;
        error_overflow <= error_overflow_next;
    end
end

//==================================
// Data Path Registers (Pass-through)
//==================================
always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
    if (!nvdla_core_rstn) begin
        out_data_pd_reg <= 512'd0;
        out_data_pvld_reg <= 1'b0;
    end else begin
        if (data_accept) begin
            out_data_pd_reg <= nvdla_bdma_inp_data_pd;
            out_data_pvld_reg <= 1'b1;
        end else if (nvdla_bdma_out_data_prdy) begin
            out_data_pvld_reg <= 1'b0;
        end
    end
end

//==================================
// Block Result Output
//==================================
// Block is zero if no non-zero words were detected
assign nvdla_bdma_out_blk_is_zero = ~blk_has_nonzero;

// Block result valid at block boundary (BLOCK_DONE state)
// Set valid when entering BLOCK_DONE, clear when leaving or when ready is asserted
always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
    if (!nvdla_core_rstn) begin
        out_blk_is_zero_vld_reg <= 1'b0;
    end else begin
        if ((zd_state != ZD_STATE_BLOCK_DONE) && (zd_state_next == ZD_STATE_BLOCK_DONE)) begin
            // Set valid when transitioning TO BLOCK_DONE
            out_blk_is_zero_vld_reg <= 1'b1;
        end else if ((zd_state == ZD_STATE_BLOCK_DONE) && nvdla_bdma_out_blk_is_zero_rdy) begin
            // Clear when ready is asserted while in BLOCK_DONE
            out_blk_is_zero_vld_reg <= 1'b0;
        end else if ((zd_state == ZD_STATE_BLOCK_DONE) && (zd_state_next != ZD_STATE_BLOCK_DONE)) begin
            // Clear when leaving BLOCK_DONE state
            out_blk_is_zero_vld_reg <= 1'b0;
        end
    end
end

assign nvdla_bdma_out_blk_is_zero_vld = out_blk_is_zero_vld_reg;

//==================================
// Error Output
//==================================
assign nvdla_bdma_zd2reg_error_overflow = error_overflow;

endmodule // NV_NVDLA_BDMA_zero_detector
