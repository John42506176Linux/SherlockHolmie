function countMagicalPairs(n, m) {
    let count = 0;
    let smaller = Math.min(n, m);
    let larger = Math.max(n, m);
  
    for (let i = 1; i <= smaller; i++) {
      let remainder = (5 - (i % 5)) % 5; // Calculate the remainder needed for divisibility by 5
      count += Math.floor((larger + remainder) / 5);
    }
  
    return count;
  }
  
  // Example usage:
  let numApples = 12;
  let numBerries = 15;
  let magicalPairCount = countMagicalPairs(numApples, numBerries);
  console.log(`Number of magical pairs: ${magicalPairCount}`);