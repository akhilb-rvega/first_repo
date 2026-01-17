# Yosys synthesis script for NV_NVDLA_BDMA_zero_detector
# Run from project root with: yosys -s tests/synth.tcl
# Minimal version - only includes files required for zero detector module

# Read the zero detector RTL (main module)
read_verilog -I sources/vmod/include sources/vmod/nvdla/bdma/NV_NVDLA_BDMA_zero_detector.v

# Elaborate design hierarchy
hierarchy -check -top NV_NVDLA_BDMA_zero_detector

# Synthesis check
check -noinit -initdrv -assert

# High-level synthesis
proc; opt; fsm; opt; memory; opt

# Mapping to internal cell library
techmap; opt

# Generic synthesis
synth -top NV_NVDLA_BDMA_zero_detector
clean

# Show statistics
stat

# Write synthesized design
write_verilog -noattr netlist.v
