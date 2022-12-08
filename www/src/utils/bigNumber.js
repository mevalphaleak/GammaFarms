import { BigNumber } from '@ethersproject/bignumber';

export const E18 = BigNumber.from("1000000000000000000");

export function formatUnits(a, decimals, precision) {
  decimals = decimals != null ? decimals : 18;
  precision = precision != null ? precision : 4;
  const aBig = toBigNumber(a);
  if (aBig.isZero()) {
    return "0";
  }
  const decBig = BigNumber.from('10').pow(BigNumber.from(decimals));
  let i = aBig.div(decBig).toString();
  let f = aBig.mod(decBig).toString();
  i = i.replace(/(\d)(?=(\d\d\d)+(?!\d))/g, function($1) { return $1 + "," });
  f = f.substring(0, precision);
  return f === "0" ? i : (i + "." + f);
}

export function toBigNumber(n) {
  return BigNumber.from(n.toString());
}