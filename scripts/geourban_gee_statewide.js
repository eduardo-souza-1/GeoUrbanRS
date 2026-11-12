// GeoUrban RS: todos os municípios, tabelas; não exporta o raster nacional.
// Importe RS_Municipios_2024.zip como Table asset e ajuste apenas esta linha.
var BOUNDARIES_ASSET = 'projects/SEU_PROJETO/assets/RS_Municipios_2024';
var regions = ee.FeatureCollection(BOUNDARIES_ASSET);
var source = ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3');
var crs = 'PROJCS["GeoUrban LAEA",GEOGCS["GRS80",DATUM["GRS80",SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["latitude_of_center",-30],PARAMETER["longitude_of_center",-53],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1]]';
var bands=[];
for(var y=1985;y<=2025;y++) bands.push('classification_'+y);
var all=source.select(bands);
var domain=all.mask().reduce(ee.Reducer.min())
  .and(all.neq(0).reduce(ee.Reducer.min()))
  .and(all.neq(27).reduce(ee.Reducer.min()));
var area=ee.Image.pixelArea().divide(10000);
var seen=source.select('classification_1985').eq(24);
var metrics=ee.Image([]);
var origins=[3,4,5,6,9,11,12,13,14,15,18,19,20,21,22,23,25,26,29,30,31,32,33,35,36,39,40,41,46,47,48,49,50,62];
// Une même domain anual: evita converter ausência de dados em expansão.
for(var year=1985;year<=2025;year++){
  var current=source.select('classification_'+year);
  var urban=current.eq(24);
  metrics=metrics.addBands(urban.multiply(area).updateMask(domain).rename('urban_'+year));
  if(year>1985){
    var prior=source.select('classification_'+(year-1));
    var gain=prior.neq(24).and(urban);
    var loss=prior.eq(24).and(urban.not());
    var first=gain.and(seen.not());
    metrics=metrics.addBands(gain.multiply(area).updateMask(domain).rename('entry_'+year))
      .addBands(loss.multiply(area).updateMask(domain).rename('exit_'+year))
      .addBands(first.multiply(area).updateMask(domain).rename('first_'+year));
    seen=seen.or(urban);
  }
}
metrics=metrics.addBands(domain.multiply(area).rename('valid_area_ha'));
// 499 inclui 2 áreas operacionais: preservar na soma, excluir de rankings.
print('Contagem esperada: 499 feições',regions.size());
print('Municípios esperados: 497',regions.filter(ee.Filter.neq('CD_MUN','4300001')).filter(ee.Filter.neq('CD_MUN','4300002')).size());
// Uma tabela ampla com 499 linhas. tileScale reduz memória por bloco.
var result=metrics.reduceRegions({collection:regions,reducer:ee.Reducer.sum(),
  crs:crs,scale:30,tileScale:4,maxPixelsPerRegion:1e10});
result=result.map(function(f){return f.setGeometry(null);});
Export.table.toDrive({collection:result,description:'GeoUrban_RS_urban_series_col11',fileFormat:'CSV'});
// Conferência independente sobre união: não apenas soma da tabela municipal.
var state=ee.FeatureCollection([ee.Feature(regions.geometry(),{scope:'RS_union'})]);
var totals=metrics.reduceRegions({collection:state,reducer:ee.Reducer.sum(),crs:crs,scale:30,tileScale:4,maxPixelsPerRegion:1e10});
Export.table.toDrive({collection:totals.map(function(f){return f.setGeometry(null);}),description:'GeoUrban_RS_reconciliation_col11',fileFormat:'CSV'});
// Origens da primeira conversão, agregadas em 1986–2025 (ano anterior imediato).
var priorOrigins=ee.Image([]);
seen=source.select('classification_1985').eq(24);
var origin=ee.Image(0);
for(var t=1986;t<=2025;t++){
 var prev=source.select('classification_'+(t-1));
 var now=source.select('classification_'+t).eq(24);
 var firstTime=now.and(seen.not()).and(prev.neq(24));
 origin=origin.where(firstTime,prev);
 seen=seen.or(now);
}
origins.forEach(function(c){priorOrigins=priorOrigins.addBands(origin.eq(c).multiply(area).updateMask(domain).rename('origin_'+c));});
var originTable=priorOrigins.reduceRegions({collection:regions,reducer:ee.Reducer.sum(),crs:crs,scale:30,tileScale:4,maxPixelsPerRegion:1e10});
Export.table.toDrive({collection:originTable.map(function(f){return f.setGeometry(null);}),description:'GeoUrban_RS_first_origins_col11',fileFormat:'CSV'});
// Preparação somente: validar o asset e executar as três tarefas em Tasks.
