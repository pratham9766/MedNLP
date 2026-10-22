import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPatientDocumentGuide, buildPatientLabGuide, patientFriendlyComparisonReason, type PatientGuideItem } from './patientGuide.ts';

const samples:PatientGuideItem[]=[
  {id:'lab-high',entity_type:'laboratory_result',analyte:'Glucose',original_text:'Glucose 180 mg/dL',comparison_status:'above_reported_range',review_status:'needs_review',lab_reported_flag:'H'},
  {id:'lab-within',entity_type:'laboratory_result',analyte:'Sodium',original_text:'Sodium 139 mmol/L',comparison_status:'within_reported_range',review_status:'reviewed'},
  {id:'lab-na',entity_type:'laboratory_result',analyte:'Culture',original_text:'Culture positive',comparison_status:'comparison_unavailable',review_status:'needs_review'},
  {id:'dx',entity_type:'diagnosis_or_symptom',original_text:'The report documents cough.',review_status:'needs_review'},
  {id:'possible',entity_type:'diagnosis_or_symptom',original_text:'A viral infection remains possible.',review_status:'needs_review',uncertain:true},
  {id:'negative',entity_type:'radiology_finding',original_text:'No pleural effusion is seen.',review_status:'needs_review',negated:true},
  {id:'past',entity_type:'diagnosis_or_symptom',original_text:'History of asthma.',review_status:'needs_review',temporality:'historical'},
  {id:'follow',entity_type:'follow_up',original_text:'Follow-up was requested.',review_status:'needs_review'},
];

test('lab guide groups printed-range comparisons, unavailable values, and lab flags separately',()=>{
  const guide=buildPatientLabGuide(samples);
  assert.equal(guide.total,3);
  assert.deepEqual(guide.outside.map(item=>item.id),['lab-high']);
  assert.deepEqual(guide.within.map(item=>item.id),['lab-within']);
  assert.deepEqual(guide.unavailable.map(item=>item.id),['lab-na']);
  assert.deepEqual(guide.labFlagged.map(item=>item.id),['lab-high']);
});

test('document guide separates mentioned facts, uncertainty, negation, history, and follow-up',()=>{
  const sections=buildPatientDocumentGuide(samples,'discharge');
  const grouped=Object.fromEntries(sections.map(section=>[section.key,section.items.map(item=>item.id)]));
  assert.deepEqual(grouped['report-facts'],['dx']);
  assert.deepEqual(grouped.uncertain,['possible']);
  assert.deepEqual(grouped.absent,['negative']);
  assert.deepEqual(grouped.historical,['past']);
  assert.deepEqual(grouped['next-steps'],['follow']);
});

test('radiology findings are grouped separately from recommendations',()=>{
  const sections=buildPatientDocumentGuide([
    {id:'finding',entity_type:'radiology_impression',original_text:'Small opacity is described.',review_status:'needs_review'},
    {id:'rec',entity_type:'radiology_recommendation',original_text:'Follow-up imaging may be considered.',review_status:'needs_review',uncertain:true},
  ],'radiology');
  assert.deepEqual(sections.map(section=>section.key),['report-facts','uncertain','next-steps']);
  assert.equal(sections[0].items[0].id,'finding');
  assert.equal(sections[2].items[0].id,'rec');
});

test('technical comparison limitations are explained in patient-friendly language',()=>{
  assert.equal(patientFriendlyComparisonReason('No reported reference interval was supplied.'),'A readable numeric reference range was not available in the report.');
  assert.equal(patientFriendlyComparisonReason('Result unit is incompatible with reference interval unit.'),'The result and printed range use different units.');
  assert.equal(patientFriendlyComparisonReason('Result is not a parseable numeric value.'),'The result is not a simple number that can be compared with a range.');
});
