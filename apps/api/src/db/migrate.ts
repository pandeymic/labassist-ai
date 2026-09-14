import fs from 'fs'; import path from 'path'; import { pool } from './store';
if(!pool){ console.log('No DATABASE_URL; migration skipped for preview mode.'); process.exit(0); }
const db=pool;
const migrationDir=path.join(__dirname,'../../migrations');
const migrations=fs.readdirSync(migrationDir).filter(file=>file.endsWith('.sql')).sort();
Promise.all(migrations.map(file=>db.query(fs.readFileSync(path.join(migrationDir,file),'utf8')))).then(()=>{console.log(`Applied ${migrations.length} migrations`); return db.end();}).catch(e=>{console.error(e);process.exit(1);});
