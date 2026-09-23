// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module opentitan_debug_replay;
  parameter bit BAD_GRANT=0, BAD_CLEAR=0;
  logic clk_i=0, rst_ni=1, state_valid=0, dev=0, prod_end=0;
  logic [3:0] secrets=0, observed_debug, observed_clear;
  logic [15:0] fsm=0;
  logic bad;
  logic [32:0] vectors[0:5];
  logic [3:0] expected_debug, expected_clear;
  logic expected_bad;
  string witness;
  opentitan_debug_formal #(.BAD_GRANT(BAD_GRANT), .BAD_CLEAR(BAD_CLEAR)) harness(.*);
  initial begin
    if (!$value$plusargs("WITNESS=%s",witness)) $fatal(1,"missing witness");
    $readmemb(witness,vectors);
    for (integer i=0;i<6;i++) begin
      {rst_ni,state_valid,dev,prod_end,secrets,fsm,expected_debug,expected_clear,expected_bad}=vectors[i];
      #2;
      if (observed_debug !== expected_debug || bad !== expected_bad || observed_clear !== expected_clear)
        $fatal(1,"witness mismatch step %0d: debug=%b expected=%b bad=%b expected=%b clear=%b expected=%b",
               i+1,observed_debug,expected_debug,bad,expected_bad,observed_clear,expected_clear);
      clk_i=1; #2; clk_i=0; #1;
    end
    $display("PASS: six-step witness replay BAD_GRANT=%0d",BAD_GRANT);
    $finish;
  end
endmodule
