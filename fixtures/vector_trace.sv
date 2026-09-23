// SPDX-License-Identifier: Apache-2.0
// Four-state VCD format oracle; not an application design or lifecycle model.
`timescale 1ns/1ps
module tb;
  reg rst_n=1, req=1, grant=0;
  reg [3:0] lc=4'b1010;
  initial begin
    $dumpfile("vector.vcd"); $dumpvars(0,tb);
    #5; lc=4'b0101; grant=1;
    #3;
    if ($test$plusargs("X")) lc=4'b10x0;
    if ($test$plusargs("Z")) lc=4'b10z0;
    #1; $finish;
  end
endmodule
