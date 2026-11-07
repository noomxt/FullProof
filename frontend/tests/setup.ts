import {createHash} from 'node:crypto';
import {sha256} from 'ethers';

// Node returns a Buffer from another realm under jsdom. Hex keeps the
// real SHA-256 implementation compatible with ethers' browser byte checks.
sha256.register(data => '0x' + createHash('sha256').update(data).digest('hex'));
