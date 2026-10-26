import { defineConfig } from "hardhat/config";
// npm run compile uses pinned solc-js; no extra compiler download needed.
export default defineConfig({
  solidity: { version: "0.8.34", settings: { optimizer: { enabled: true, runs: 200 }, viaIR: true, evmVersion: "cancun" } },
  networks: {
    localhost: { type: "http", url: "http://127.0.0.1:8545", chainId: 31337 },
    hardhatMainnet: { type: "edr-simulated", chainType: "l1", chainId: 31337 }
  }
});
