import test from 'node:test';
import assert from 'node:assert/strict';
import { comparisonLabel, evidenceMatches, filterLabResults, labMetrics, rangeBarModel, type LabResultLike } from './labComparison.ts';

const items:LabResultLike[]=[
  {id:'a',entity_type:'laboratory_result',analyte:'Glucose',original_text:'Glucose 100 mg/dL',numeric_value:100,unit:'mg/dL',reference_low:70,reference_high:99,comparison_status:'above_reported_range',review_status:'needs_review'},
  {id:'b',entity_type:'laboratory_result',analyte:'Sodium',original_text:'Sodium 140 mmol/L',numeric_value:140,unit:'mmol/L',reference_low:135,reference_high:145,comparison_status:'within_reported_range',review_status:'reviewed'},
  {id:'c',entity_type:'laboratory_result',analyte:'Culture',original_text:'Culture positive',qualitative_value:'positive',comparison_status:'comparison_unavailable',review_status:'needs_review'},
  {id:'d',entity_type:'radiology_finding',original_text:'Opacity',review_status:'needs_review'},
];

test('summary metrics use actual items and keep needs-review as an overlapping count',()=>{
  assert.deepEqual(labMetrics(items),{all:3,within_reported_range:1,below_reported_range:0,above_reported_range:1,comparison_unavailable:1,needs_review:2});
});

test('filters apply to the extracted lab list and search test names',()=>{
  assert.deepEqual(filterLabResults(items,'above_reported_range').map(item=>item.id),['a']);
  assert.deepEqual(filterLabResults(items,'needs_review','culture').map(item=>item.id),['c']);
  assert.deepEqual(filterLabResults(items,'all','sodium').map(item=>item.id),['b']);
  assert.deepEqual(filterLabResults(items,'below_reported_range'),[]);
});

test('range bar uses backend bounds and places the out-of-range marker from the actual value',()=>{
  const model=rangeBarModel(items[0]);
  assert.ok(model);
  assert.equal(model.low,70); assert.equal(model.high,99); assert.equal(model.value,100);
  assert.ok(model.marker>model.end&&model.marker<100);
});

test('range bar is omitted for unavailable, comparator, qualitative, or invalid ranges',()=>{
  assert.equal(rangeBarModel(items[2]),null);
  assert.equal(rangeBarModel({...items[0],comparator:'>'}),null);
  assert.equal(rangeBarModel({...items[0],reference_high:70}),null);
  assert.equal(rangeBarModel({...items[0],comparison_status:'comparison_unavailable'}),null);
});

test('evidence links only count as precise when the source span matches exactly',()=>{
  const item={...items[0],source_page:1,span_start:0,span_end:17};
  assert.equal(evidenceMatches(item,[{page:1,text:'Glucose 100 mg/dL'}]),true);
  assert.equal(evidenceMatches({...item,span_end:16},[{page:1,text:'Glucose 100 mg/dL'}]),false);
  assert.equal(comparisonLabel('comparison_unavailable'),'Comparison unavailable');
});
