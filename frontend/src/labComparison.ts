export type LabComparisonStatus = 'within_reported_range' | 'below_reported_range' | 'above_reported_range' | 'comparison_unavailable';
export type LabFilter = 'all' | LabComparisonStatus | 'needs_review';

export type LabResultLike = {
  id:string;
  entity_type:string;
  analyte?:string|null;
  original_text:string;
  numeric_value?:number|null;
  comparator?:string|null;
  qualitative_value?:string|null;
  unit?:string|null;
  reference_interval?:string|null;
  reference_low?:number|null;
  reference_high?:number|null;
  comparison_status?:LabComparisonStatus;
  review_status:string;
};

export type LabMetrics = Record<LabFilter, number>;
export type RangeBarModel = { start:number; end:number; marker:number; low:number; high:number; value:number };

export function comparisonLabel(status?:LabComparisonStatus):string {
  switch(status){
    case 'within_reported_range': return 'Within reported range';
    case 'below_reported_range': return 'Below reported range';
    case 'above_reported_range': return 'Above reported range';
    default: return 'Comparison unavailable';
  }
}

export function labMetrics(items:LabResultLike[]):LabMetrics {
  const lab=items.filter(item=>item.entity_type==='laboratory_result');
  const metrics:LabMetrics={all:lab.length,within_reported_range:0,below_reported_range:0,above_reported_range:0,comparison_unavailable:0,needs_review:0};
  for(const item of lab){
    const status=item.comparison_status||'comparison_unavailable';
    metrics[status]+=1;
    if(item.review_status==='needs_review') metrics.needs_review+=1;
  }
  return metrics;
}

export function filterLabResults<T extends LabResultLike>(items:T[],filter:LabFilter,query=''):T[]{
  const needle=query.trim().toLocaleLowerCase();
  return items.filter(item=>{
    if(item.entity_type!=='laboratory_result') return false;
    const status=item.comparison_status||'comparison_unavailable';
    if(filter==='needs_review'&&item.review_status!=='needs_review') return false;
    if(filter!=='all'&&filter!=='needs_review'&&status!==filter) return false;
    return !needle||`${item.analyte||''} ${item.original_text}`.toLocaleLowerCase().includes(needle);
  });
}

export function rangeBarModel(item:LabResultLike):RangeBarModel|null {
  const {comparison_status:status,numeric_value:value,reference_low:low,reference_high:high,unit,comparator,qualitative_value}=item;
  if(!status||status==='comparison_unavailable'||value==null||!Number.isFinite(value)||low==null||high==null||!Number.isFinite(low)||!Number.isFinite(high)||high<=low||!unit||comparator||qualitative_value) return null;
  const padding=Math.max((high-low)*0.25,Math.abs(high)*0.02,0.01);
  const scaleMin=Math.min(low,value)-padding;
  const scaleMax=Math.max(high,value)+padding;
  const scale=scaleMax-scaleMin;
  if(!Number.isFinite(scale)||scale<=0) return null;
  const percent=(n:number)=>Math.max(0,Math.min(100,((n-scaleMin)/scale)*100));
  return {start:percent(low),end:percent(high),marker:percent(value),low,high,value};
}

export function evidenceMatches(item:LabResultLike & {source_page?:number|null;span_start?:number|null;span_end?:number|null},pages:{page:number;text:string}[]):boolean {
  if(item.source_page==null||item.span_start==null||item.span_end==null||item.span_start<0||item.span_end<=item.span_start) return false;
  const source=pages.find(page=>page.page===item.source_page)?.text;
  return source!=null&&source.slice(item.span_start,item.span_end)===item.original_text;
}
