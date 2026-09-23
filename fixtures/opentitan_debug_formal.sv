// SPDX-License-Identifier: Apache-2.0
// External property harness. Real decoder and generic sender flops are unchanged.
module opentitan_debug_formal import lc_ctrl_pkg::*; import lc_ctrl_state_pkg::*; #(
  parameter bit BAD_GRANT=0, BAD_CLEAR=0
) (
  input logic clk_i, rst_ni, state_valid, dev, prod_end,
  input logic [3:0] secrets,
  input logic [15:0] fsm,
  output logic bad,
  output logic [3:0] observed_debug, observed_clear
);
  lc_tx_t debug_en, debug_clr;
  lc_state_e selected_state;
  assign selected_state = dev ? LcStDev : prod_end ? LcStProdEnd : LcStProd;
  lc_ctrl_signal_decode dut (
    .clk_i, .rst_ni, .lc_state_valid_i(state_valid), .lc_state_i(selected_state),
    .fsm_state_i(fsm_state_e'(fsm)), .secrets_valid_i(lc_tx_t'(secrets)),
    .lc_hw_debug_en_o(debug_en),
    .lc_raw_test_rma_o(), .lc_init_done_o(), .lc_dft_en_o(), .lc_nvm_debug_en_o(),
    .lc_hw_debug_clr_o(debug_clr), .lc_cpu_en_o(), .lc_creator_seed_sw_rw_en_o(),
    .lc_owner_seed_sw_rw_en_o(), .lc_iso_part_sw_rd_en_o(), .lc_iso_part_sw_wr_en_o(),
    .lc_seed_hw_rd_en_o(), .lc_rma_state_o(), .lc_keymgr_en_o(), .lc_escalate_en_o(),
    .lc_keymgr_div_o()
  );
  // Separate one-cycle RTL-derived reference, including valid gating.
  logic expected_on, expected_clear, history_valid;
  logic broadcasting;
  assign broadcasting = fsm inside {IdleSt, ClkMuxSt, CntIncrSt, CntProgSt,
      TransCheckSt, NvmRmaSt, TokenHashSt, TokenCheck0St, TokenCheck1St, TransProgSt};
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin expected_on <= 0; expected_clear <= 0; history_valid <= 0; end
    else begin
      expected_on <= broadcasting && state_valid && dev;
      expected_clear <= (fsm != ResetSt) && !(broadcasting && state_valid);
      history_valid <= 1;
    end
  end
  assign observed_debug = BAD_GRANT ? 4'b0101 : debug_en;
  assign observed_clear = BAD_CLEAR ? 4'b1010 : debug_clr;
  assign bad = rst_ni && history_valid &&
               ((observed_debug != (expected_on ? 4'b0101 : 4'b1010)) ||
                (observed_clear != (expected_clear ? 4'b0101 : 4'b1010)));
endmodule
