import type { LabResultLike } from './labComparison';

export type PatientGuideItem = LabResultLike & {
  source_page?:number|null;
  negated?:boolean;
  uncertain?:boolean;
  temporality?:string;
  lab_reported_flag?:string|null;
  comparison_note?:string|null;
};

export type PatientGuideSection = { key:string; title:string; description:string; items:PatientGuideItem[] };

export function patientFriendlyComparisonReason(note?:string|null):string {
  const text=(note||'').toLocaleLowerCase();
  if(text.includes('unit is missing')) return 'A unit is missing, so the value cannot be safely matched to the printed range.';
  if(text.includes('unit is incompatible')) return 'The result and printed range use different units.';
  if(text.includes('qualitative')) return 'This is a text result rather than a number.';
  if(text.includes('comparator')||text.includes('inequalit')) return 'The result uses a less-than or greater-than sign, so a simple range comparison is not shown.';
  if(text.includes('reference interval')&&(text.includes('not found')||text.includes('could not be parsed')||text.includes('not provided')||text.includes('not supplied')||text.includes('no reported'))) return 'A readable numeric reference range was not available in the report.';
  if(text.includes('range bounds')||text.includes('separator')) return 'The printed range could not be read reliably as two numeric limits.';
  if(text.includes('numeric value')||text.includes('parseable')) return 'The result is not a simple number that can be compared with a range.';
  return 'The report information was not enough to compare this result reliably.';
}

export function patientLabValue(item:PatientGuideItem):string {
  if(item.numeric_value!=null&&Number.isFinite(item.numeric_value)) return `${item.comparator||''}${item.numeric_value}${item.unit?` ${item.unit}`:''}`;
  if(item.qualitative_value) return item.qualitative_value;
  return item.original_text;
}

export function patientComparisonSummary(item:PatientGuideItem):string {
  switch(item.comparison_status){
    case 'above_reported_range': return 'Higher than the range printed by this laboratory.';
    case 'below_reported_range': return 'Lower than the range printed by this laboratory.';
    case 'within_reported_range': return 'Within the range printed by this laboratory. This comparison alone does not determine what is healthy for you.';
    default: return item.qualitative_value
      ? 'This is a text result, so a numeric range comparison does not apply.'
      : `A reliable comparison with the laboratory range could not be made. ${patientFriendlyComparisonReason(item.comparison_note)}`;
  }
}

export function patientDiscussionQuestions(documentType:string):string[]{
  if(documentType==='radiology') return [
    'How do the findings in this report fit with my symptoms and health history?',
    'Does the report suggest any follow-up, and has it been arranged?',
  ];
  if(documentType==='laboratory') return [
    'How do these results fit with my symptoms, health history, and other results?',
    'Is there any result that needs follow-up for me?',
  ];
  return [
    'Which parts of this report or plan should I pay attention to?',
    'Has the follow-up mentioned in this report been scheduled or completed?',
  ];
}

export function buildPatientLabGuide(items:PatientGuideItem[]){
  const labs=items.filter(item=>item.entity_type==='laboratory_result');
  const outside=labs.filter(item=>item.comparison_status==='above_reported_range'||item.comparison_status==='below_reported_range');
  const within=labs.filter(item=>item.comparison_status==='within_reported_range');
  const unavailable=labs.filter(item=>!item.comparison_status||item.comparison_status==='comparison_unavailable');
  const labFlagged=labs.filter(item=>Boolean(item.lab_reported_flag));
  return {total:labs.length,outside,within,unavailable,labFlagged};
}

export function buildPatientDocumentGuide(items:PatientGuideItem[],documentType:string):PatientGuideSection[]{
  const active=items.filter(item=>item.entity_type!=='laboratory_result');
  const sourceFacts=active.filter(item=>{
    if(item.uncertain||item.negated||item.temporality==='historical') return false;
    return documentType==='radiology'
      ? ['radiology_finding','radiology_impression'].includes(item.entity_type)
      : item.entity_type==='diagnosis_or_symptom';
  });
  const uncertain=active.filter(item=>item.uncertain);
  const absent=active.filter(item=>item.negated&&!item.uncertain);
  const historical=active.filter(item=>item.temporality==='historical'&&!item.uncertain&&!item.negated);
  const medicines=active.filter(item=>item.entity_type==='medication');
  const nextSteps=active.filter(item=>item.entity_type==='follow_up'||item.entity_type==='radiology_recommendation');
  const allergies=active.filter(item=>item.entity_type==='allergy');
  const sections:PatientGuideSection[]=[
    {key:'report-facts',title:documentType==='radiology'?'Imaging findings and impression':'Symptoms or conditions mentioned',description:'Statements extracted from the report.',items:sourceFacts},
    {key:'uncertain',title:'Uncertain or under consideration',description:'The report uses uncertain wording for these statements.',items:uncertain},
    {key:'absent',title:'Findings the report says were absent',description:'These are documented negative findings, not proof that a condition is impossible.',items:absent},
    {key:'historical',title:'Past history mentioned',description:'The report describes these as historical rather than current.',items:historical},
    {key:'medicines',title:'Medicines mentioned',description:'The source wording is preserved; check the original instructions.',items:medicines},
    {key:'next-steps',title:'Follow-up or recommendations written in the report',description:'A request or recommendation does not mean an appointment or action was completed.',items:nextSteps},
    {key:'allergies',title:'Allergies mentioned',description:'Allergy statements are copied from the source record.',items:allergies},
  ];
  return sections.filter(section=>section.items.length>0);
}
