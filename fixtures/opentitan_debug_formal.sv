// SPDX-License-Identifier: Apache-2.0
// External property harness. Real decoder and generic sender flops are unchanged.
module opentitan_debug_formal import lc_ctrl_pkg::*; import lc_ctrl_state_pkg::*; #(
  parameter bit BAD_GRANT=0
) (
  input logic clk_i, rst_ni, state_valid, dev, prod_end,
  input logic [3:0] secrets,
  output logic bad,
  output logic [3:0] observed_debug
);
  lc_tx_t debug_en;
  lc_state_e selected_state;
  assign selected_state = dev ? LcStDev : prod_end ? LcStProdEnd : LcStProd;
  lc_ctrl_signal_decode dut (
    .clk_i, .rst_ni, .lc_state_valid_i(state_valid), .lc_state_i(selected_state),
    .fsm_state_i(IdleSt), .secrets_valid_i(lc_tx_t'(secrets)),
    .lc_hw_debug_en_o(debug_en),
    .lc_raw_test_rma_o(), .lc_init_done_o(), .lc_dft_en_o(), .lc_nvm_debug_en_o(),
    .lc_hw_debug_clr_o(), .lc_cpu_en_o(), .lc_creator_seed_sw_rw_en_o(),
    .lc_owner_seed_sw_rw_en_o(), .lc_iso_part_sw_rd_en_o(), .lc_iso_part_sw_wr_en_o(),
    .lc_seed_hw_rd_en_o(), .lc_rma_state_o(), .lc_keymgr_en_o(), .lc_escalate_en_o(),
    .lc_keymgr_div_o()
  );
  // Independent one-cycle architectural reference, including valid gating.
  logic expected_on, history_valid;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin expected_on <= 0; history_valid <= 0; end
    else begin expected_on <= state_valid && dev; history_valid <= 1; end
  end
  assign observed_debug = BAD_GRANT ? 4'b0101 : debug_en;
  assign bad = rst_ni && history_valid &&
               (observed_debug != (expected_on ? 4'b0101 : 4'b1010));
endmodule
