import { randomUUID } from 'crypto';
import { pool, Provider, Patient, Appointment, Claim, Audit } from './store';

const provider = (row:Record<string, unknown>):Provider => ({id:String(row.id),name:String(row.name),specialty:String(row.specialty),location:String(row.location),active:Boolean(row.active)});
const patient = (row:Record<string, unknown>):Patient => ({id:String(row.id),displayName:String(row.display_name),birthYear:Number(row.birth_year),coverage:String(row.coverage)});
const appointment = (row:Record<string, unknown>):Appointment => ({id:String(row.id),providerId:String(row.provider_id),patientId:String(row.patient_id),startsAt:new Date(String(row.starts_at)).toISOString(),endsAt:new Date(String(row.ends_at)).toISOString(),status:row.status as Appointment['status'],reason:String(row.reason),createdBy:String(row.created_by)});
const claim = (row:Record<string, unknown>):Claim => ({id:String(row.id),patientId:String(row.patient_id),providerId:String(row.provider_id),appointmentId:String(row.appointment_id),amountCents:Number(row.amount_cents),status:row.status as Claim['status'],submittedAt:new Date(String(row.submitted_at)).toISOString(),updatedAt:new Date(String(row.updated_at)).toISOString()});
const auditLog = (row:Record<string, unknown>):Audit => ({id:String(row.id),actor:String(row.actor),action:String(row.action),entityType:String(row.entity_type),entityId:String(row.entity_id),metadata:(row.metadata||{}) as Record<string,unknown>,createdAt:new Date(String(row.created_at)).toISOString()});

export const databaseEnabled = Boolean(pool);
export async function listProviders(search=''){ if(!pool)return null; const result=await pool.query('SELECT * FROM providers WHERE name ILIKE $1 OR specialty ILIKE $1 OR location ILIKE $1 ORDER BY name ASC',['%'+search+'%']); return result.rows.map(provider); }
export async function listPatients(search=''){ if(!pool)return null; const result=await pool.query('SELECT * FROM patients WHERE display_name ILIKE $1 OR coverage ILIKE $1 ORDER BY display_name ASC',['%'+search+'%']); return result.rows.map(patient); }
export async function listAppointments(status?:string,providerId?:string){ if(!pool)return null; const result=await pool.query('SELECT * FROM appointments WHERE ($1::text IS NULL OR status=$1) AND ($2::text IS NULL OR provider_id=$2) ORDER BY starts_at ASC',[status||null,providerId||null]); return result.rows.map(appointment); }
export async function listClaims(status?:string){ if(!pool)return null; const result=await pool.query('SELECT * FROM claims WHERE ($1::text IS NULL OR status=$1) ORDER BY updated_at DESC',[status||null]); return result.rows.map(claim); }
export async function listAuditLogs(){ if(!pool)return null; const result=await pool.query('SELECT * FROM audit_logs ORDER BY created_at DESC'); return result.rows.map(auditLog); }
export async function insertAudit(actor:string,action:string,entityType:string,entityId:string,metadata:Record<string,unknown>={}){ if(pool) await pool.query('INSERT INTO audit_logs (id,actor,action,entity_type,entity_id,metadata) VALUES ($1,$2,$3,$4,$5)',[randomUUID(),actor,action,entityType,entityId,metadata]); }
export { provider, patient, appointment, claim };
