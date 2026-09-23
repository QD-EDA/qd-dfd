// SPDX-License-Identifier: Apache-2.0
module opentitan_dmi_formal import lc_ctrl_pkg::*; #(
  parameter bit BAD_GRANT=0
) (
  input logic clk_i, rst_ni, strap,
  input logic [3:0] enable, clear_debug, bypass, escalate,
  output logic observed_enable, bad
);
  rv_dm_dmi_gate #(.SecVolatileRawUnlockEn(0)) dut (
    .clk_i, .rst_ni, .strap_en_i(strap), .strap_en_override_i(1'b0),
    .lc_hw_debug_en_i(lc_tx_t'(enable)), .lc_hw_debug_clr_i(lc_tx_t'(clear_debug)),
    .lc_check_byp_en_i(lc_tx_t'(bypass)), .lc_escalate_en_i(lc_tx_t'(escalate)),
    .dbg_tl_h2d_win_i('0), .dbg_tl_d2h_win_o(),
    .dmi_req_valid_o(), .dmi_req_ready_i(1'b0), .dmi_req_o(),
    .dmi_rsp_valid_i(1'b0), .dmi_rsp_ready_o(), .dmi_rsp_i('0), .intg_error_o()
  );
  // Separate Boolean reference: two sampled synchronization stages, then retention.
  logic [15:0] controls_meta, controls_sync;
  logic expected_enable;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      controls_meta <= 16'haaaa;
      controls_sync <= 16'haaaa;
      expected_enable <= 0;
    end else begin
      controls_meta <= {enable, clear_debug, bypass, escalate};
      controls_sync <= controls_meta;
      expected_enable <= ((strap && controls_sync[15:12] == 4'h5) || expected_enable)
                         && controls_sync[11:0] == 12'haaa;
    end
  end
  assign observed_enable = BAD_GRANT ? 1'b1 : dut.dmi_en;
  assign bad = rst_ni && (observed_enable != expected_enable);
endmodule
