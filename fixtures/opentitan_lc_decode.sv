// SPDX-License-Identifier: Apache-2.0
// QD harness using the unmodified pinned OpenTitan package implementation.
`timescale 1ns/1ps
module opentitan_lc_decode;
  import lc_ctrl_pkg::*;
  logic rst_n=0, request=1;
  lc_tx_t lc=Off;
  logic decoded, grant;
  assign decoded = lc_tx_test_true_strict(lc);
  assign grant = ($test$plusargs("BAD_GRANT") && lc == lc_tx_t'(0)) ? 1'b1 : decoded;
  initial begin
    $dumpfile("lc_decode.vcd"); $dumpvars(0,opentitan_lc_decode);
    #1; rst_n=1;
    for (int i=0;i<16;i++) begin
      lc=lc_tx_t'(i);
      #1;
      // Independent expected truth table, from the pinned On encoding (0101).
      if (decoded !== (i==5)) $fatal(1,"OpenTitan strict decode mismatch");
      #1;
    end
    $display("TRACE: all 16 strict decode encodings exercised");
    $finish;
  end
endmodule
