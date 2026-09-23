// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module opentitan_dmi_replay;
  parameter bit BAD_GRANT=0;
  logic clk_i=0, rst_ni=1, strap=0;
  logic [3:0] enable=10, clear_debug=10, bypass=10, escalate=10;
  logic observed_enable, bad, expected_enable, expected_bad;
  logic [19:0] vectors[0:9];
  string witness;
  opentitan_dmi_formal #(.BAD_GRANT(BAD_GRANT)) harness(.*);
  initial begin
    if (!$value$plusargs("WITNESS=%s", witness)) $fatal(1,"missing witness");
    $readmemb(witness, vectors);
    for (integer i=0; i<10; i++) begin
      {rst_ni,strap,enable,clear_debug,bypass,escalate,expected_enable,expected_bad}=vectors[i];
      #2;
      if (observed_enable !== expected_enable || bad !== expected_bad)
        $fatal(1,"witness mismatch step %0d: enable=%b expected=%b bad=%b expected=%b",
               i+1,observed_enable,expected_enable,bad,expected_bad);
      clk_i=1; #2; clk_i=0; #1;
    end
    $display("PASS: ten-step DMI permission witness replay");
    $finish;
  end
endmodule
