import { Pool } from 'pg';
import { randomUUID } from 'crypto';

export type Role = 'admin' | 'scheduler' | 'billing';
export type AppointmentStatus = 'scheduled' | 'checked-in' | 'completed' | 'cancelled';
export type ClaimStatus = 'submitted' | 'in-review' | 'paid' | 'denied';
export type Provider = { id:string; name:string; specialty:string; location:string; active:boolean };
export type Patient = { id:string; displayName:string; birthYear:number; coverage:string };
export type Appointment = { id:string; providerId:string; patientId:string; startsAt:string; endsAt:string; status:AppointmentStatus; reason:string; createdBy:string };
export type Claim = { id:string; patientId:string; providerId:string; appointmentId:string; amountCents:number; status:ClaimStatus; submittedAt:string; updatedAt:string };
export type Audit = { id:string; actor:string; action:string; entityType:string; entityId:string; metadata:Record<string,unknown>; createdAt:string };

export const providers: Provider[] = [
  {id:'pr-101',name:'Dr. Maya Chen',specialty:'Primary Care',location:'Downtown clinic',active:true},
  {id:'pr-102',name:'Dr. Elias Brooks',specialty:'Cardiology',location:'Riverside clinic',active:true},
  {id:'pr-103',name:'Dr. Sofia Patel',specialty:'Dermatology',location:'Northstar virtual',active:true}
];
export const patients: Patient[] = [
  {id:'pt-201',displayName:'Jordan R.',birthYear:1988,coverage:'Northstar Select'},
  {id:'pt-202',displayName:'Taylor K.',birthYear:1976,coverage:'Summit PPO'},
  {id:'pt-203',displayName:'Morgan S.',birthYear:1994,coverage:'Northstar Select'},
  {id:'pt-204',displayName:'Casey L.',birthYear:1969,coverage:'Harbor Medicare Advantage'}
];
const day = (offset:number, hour:number) => { const d = new Date(); d.setDate(d.getDate()+offset); const wholeHour=Math.floor(hour); d.setHours(wholeHour,Math.round((hour-wholeHour)*60),0,0); return d.toISOString(); };
export const appointments: Appointment[] = [
  {id:'apt-301',providerId:'pr-101',patientId:'pt-201',startsAt:day(0,9),endsAt:day(0,9.5),status:'scheduled',reason:'Annual wellness review',createdBy:'demo@northstar.test'},
  {id:'apt-302',providerId:'pr-102',patientId:'pt-202',startsAt:day(0,10),endsAt:day(0,10.75),status:'checked-in',reason:'Follow-up consultation',createdBy:'demo@northstar.test'},
  {id:'apt-303',providerId:'pr-103',patientId:'pt-203',startsAt:day(1,14),endsAt:day(1,14.5),status:'scheduled',reason:'Skin health consult',createdBy:'demo@northstar.test'},
  {id:'apt-304',providerId:'pr-101',patientId:'pt-204',startsAt:day(-1,11),endsAt:day(-1,11.5),status:'completed',reason:'Medication review',createdBy:'demo@northstar.test'}
];
export const claims: Claim[] = appointments.slice(0,4).map((a,i)=>({id:`cl-${401+i}`,patientId:a.patientId,providerId:a.providerId,appointmentId:a.id,amountCents:[18500,24000,12500,9000][i],status:(['in-review','submitted','paid','denied'] as ClaimStatus[])[i],submittedAt:a.startsAt,updatedAt:a.startsAt}));
export const auditLogs: Audit[] = [{id:'log-501',actor:'demo@northstar.test',action:'seeded_demo_data',entityType:'system',entityId:'provider-ops',metadata:{records:12},createdAt:new Date().toISOString()}];
export const pool = process.env.DATABASE_URL ? new Pool({connectionString:process.env.DATABASE_URL}) : null;
export function audit(actor:string, action:string, entityType:string, entityId:string, metadata:Record<string,unknown>={}) { auditLogs.unshift({id:randomUUID(),actor,action,entityType,entityId,metadata,createdAt:new Date().toISOString()}); }
