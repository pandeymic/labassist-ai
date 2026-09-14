import fs from 'fs'; import path from 'path'; import { pool } from './store';
if(!pool){ console.log('No DATABASE_URL; synthetic in-memory seed is active for preview mode.'); process.exit(0); }
const db=pool;
const seedPath=path.join(__dirname,'../../migrations/002_demo_seed.sql');
db.query(fs.readFileSync(seedPath,'utf8')).then(()=>{console.log('Synthetic PostgreSQL seed complete'); return db.end();}).catch(e=>{console.error(e);process.exit(1);});
