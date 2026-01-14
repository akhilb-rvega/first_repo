# Yosys synthesis script for NV_NVDLA_BDMA_zero_detector
# Run from project root with: yosys -s tests/synth.tcl

# read verilog - vlibs
read_verilog -I sources/vmod/include sources/vmod/vlibs/AN2D4PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/CKLNQD12.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/CKLNQD12PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_cdp_icvt.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_cdp_ocvt.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp16_to_fp17.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp16_to_fp32.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp17_add.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp17_mul.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp17_sub.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp17_to_fp16.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp17_to_fp32.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp32_add.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp32_mul.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp32_sub.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp32_to_fp16.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_fp32_to_fp17.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/HLS_uint16_to_fp17.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/LNQD1PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/MUX2D4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/MUX2HDD2.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_BLKBOX_BUFFER.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_BLKBOX_SINK.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_BLKBOX_SRC0.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_BLKBOX_SRC0_X.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_CLK_gate_power.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_DW02_tree.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/NV_DW_minmax.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/oneHotClk_async_read_clock.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/oneHotClk_async_write_clock.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/OR2D1.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/PGAOPV_AN2D2PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/PGAOPV_DFCNQD2PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/PGAOPV_INVD2PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/p_SDFCNQD1PO4.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/p_SSYNC2DO_C_PP.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/p_SSYNC3DO_C_PPP.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/p_STRICTSYNC3DOTM_C_PPP.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/ScanShareSel_JTAG_reg_ext_cg.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/SDFCNQD1.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/SDFQD1.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/SDFSNQD1.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/sync2d_c_pp.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/sync3d.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/sync3d_c_ppp.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/sync3d_s_ppp.v
read_verilog -I sources/vmod/include sources/vmod/vlibs/sync_reset.v

# read verilog - RAM models
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_128X11_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_128X6_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_16X256_GL_M1_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_20X288_GL_M1_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_20X80_GL_M1_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_256X4_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_256X7_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_256X8_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_32X16_GL_M1_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_32X32_GL_M1_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_64X10_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_80X14_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMDP_80X15_GL_M2_E2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_160X144_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_160X16_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_160X82_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_248X144_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_248X82_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_256X11_GL_M4_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_256X144_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_256X80_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_32X192_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_32X224_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_32X256_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_32X288_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_60X168_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_64X116_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_64X226_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_64X288_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_80X16_GL_M2_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_80X226_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_80X256_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_80X288_GL_M1_D2.v
read_verilog -I sources/vmod/include sources/vmod/rams/model/RAMPDP_80X72_GL_M1_D2.v

# read verilog - RAM synth
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_16x256.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_16x256_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x3.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x3_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x512.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x512_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x7.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_256x7_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x16.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x16_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x512.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x512_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x544.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x544_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x768.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_32x768_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_64x10.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_64x10_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_64x116.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rws_64x116_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_128x11.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_128x11_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_128x6.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_128x6_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_160x16.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_160x16_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_160x514.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_160x514_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_20x289.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_20x289_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_245x514.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_245x514_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_256x11.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_256x11_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_32x32.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_32x32_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_61x514.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_61x514_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x14.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x14_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x16.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x16_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x256.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x256_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x514.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsp_80x514_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwst_256x8.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwst_256x8_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_19x80.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_19x80_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_60x168.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_60x168_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_80x15.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_80x15_logic.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_80x72.v
read_verilog -I sources/vmod/include sources/vmod/rams/synth/nv_ram_rwsthp_80x72_logic.v

#read_verilog -I sources/verif/synth_tb sources/verif/synth_tb/*.v
#read_verilog -I sources/vmod/include sources/vmod/nvdla/pdp/*.v


# read verilog - BDMA RTL
read_verilog -I sources/vmod/include sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v

# elaborate design hierarchy
hierarchy -check -top NV_NVDLA_BDMA_zero_detector

# Synthesis check
check -noinit -initdrv -assert

# the high-level stuff
proc; opt; fsm; opt; memory; opt

# mapping to internal cell library
techmap; opt

# generic synthesis
synth -top NV_NVDLA_BDMA_zero_detector
clean

# write synthesized design
write_verilog -noattr netlist.v