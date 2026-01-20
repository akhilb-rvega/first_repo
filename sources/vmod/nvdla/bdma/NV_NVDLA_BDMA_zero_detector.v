// ================================================================
// NV_NVDLA_BDMA_zero_detector
// 8-bit per-beat zero detector
// ================================================================
module NV_NVDLA_BDMA_zero_detector (
    // Clock & Reset
    input  wire        nvdla_core_clk,
    input  wire        nvdla_core_rstn,

    // Configuration
    input  wire        nvdla_bdma_reg2zd_cfg_enable,
    input  wire [1:0]  nvdla_bdma_reg2zd_cfg_block_size, // unused

    // Error reporting
    output wire        nvdla_bdma_zd2reg_error_overflow,

    // Input stream
    input  wire [7:0]  nvdla_bdma_inp_data_pd,
    input  wire        nvdla_bdma_inp_data_pvld,
    output wire        nvdla_bdma_inp_data_prdy,

    // Output data stream
    output wire [7:0]  nvdla_bdma_out_data_pd,
    output wire        nvdla_bdma_out_data_pvld,
    input  wire        nvdla_bdma_out_data_prdy,

    // Zero-detection metadata
    output wire        nvdla_bdma_out_blk_is_zero,
    output wire        nvdla_bdma_out_blk_is_zero_vld,
    input  wire        nvdla_bdma_out_blk_is_zero_rdy
);

    // ------------------------------------------------------------
    // No overflow detection in this implementation
    // ------------------------------------------------------------
    assign nvdla_bdma_zd2reg_error_overflow = 1'b0;

    // ------------------------------------------------------------
    // Bypass mode (combinational passthrough)
    // ------------------------------------------------------------
    wire bypass = ~nvdla_bdma_reg2zd_cfg_enable;

    // ------------------------------------------------------------
    // Single-entry buffer (enabled mode)
    // ------------------------------------------------------------
    reg        buf_valid;
    reg        buf_data_vld;
    reg        buf_meta_vld;
    reg [7:0]  buf_data;
    reg        buf_zero;

    // ------------------------------------------------------------
    // Input ready logic
    // ------------------------------------------------------------
    assign nvdla_bdma_inp_data_prdy =
        bypass
            ? nvdla_bdma_out_data_prdy
            : ~buf_valid;

    // ------------------------------------------------------------
    // Output assignments
    // ------------------------------------------------------------
    assign nvdla_bdma_out_data_pd =
        bypass ? nvdla_bdma_inp_data_pd : buf_data;

    assign nvdla_bdma_out_data_pvld =
        bypass ? nvdla_bdma_inp_data_pvld : buf_data_vld;

    assign nvdla_bdma_out_blk_is_zero =
        bypass ? 1'b0 : buf_zero;

    assign nvdla_bdma_out_blk_is_zero_vld =
        bypass ? 1'b0 : buf_meta_vld;

    // ------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------
    always @(posedge nvdla_core_clk or negedge nvdla_core_rstn) begin
        if (!nvdla_core_rstn) begin
            buf_valid    <= 1'b0;
            buf_data_vld <= 1'b0;
            buf_meta_vld <= 1'b0;
            buf_data     <= 8'd0;
            buf_zero     <= 1'b0;
        end else begin
            // ----------------------------------------------------
            // Disable clears all state
            // ----------------------------------------------------
            if (!nvdla_bdma_reg2zd_cfg_enable) begin
                buf_valid    <= 1'b0;
                buf_data_vld <= 1'b0;
                buf_meta_vld <= 1'b0;
            end else begin
                // ------------------------------------------------
                // Accept new input beat
                // ------------------------------------------------
                if (!buf_valid &&
                    nvdla_bdma_inp_data_pvld &&
                    nvdla_bdma_inp_data_prdy) begin

                    buf_valid    <= 1'b1;
                    buf_data_vld <= 1'b1;
                    buf_meta_vld <= 1'b1;
                    buf_data     <= nvdla_bdma_inp_data_pd;
                    buf_zero     <= (nvdla_bdma_inp_data_pd == 8'd0);
                end

                // ------------------------------------------------
                // Data channel handshake
                // ------------------------------------------------
                if (buf_data_vld &&
                    nvdla_bdma_out_data_prdy) begin
                    buf_data_vld <= 1'b0;
                end

                // ------------------------------------------------
                // Metadata channel handshake
                // ------------------------------------------------
                if (buf_meta_vld &&
                    nvdla_bdma_out_blk_is_zero_rdy) begin
                    buf_meta_vld <= 1'b0;
                end

                // ------------------------------------------------
                // Clear buffer only after BOTH consumed
                // ------------------------------------------------
                if (buf_valid &&
                    !buf_data_vld &&
                    !buf_meta_vld) begin
                    buf_valid <= 1'b0;
                end
            end
        end
    end

endmodule
