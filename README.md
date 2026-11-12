# GeoUrban RS

Como a expansão urbana transformou coberturas não urbanas no Rio Grande do Sul entre 1985 e 2025?

**Estado:** pipeline tabular e piloto raster anual validados. Porto Alegre completa foi processada com limites IBGE 2024; as exportações estaduais foram submetidas e ainda precisam ser concluídas e verificadas. O MVP estadual está em desenvolvimento.

## Primeiro resultado

A área classificada como urbana nas tabelas oficiais passa de **146.402,52 ha (1985)** para **288.351,54 ha (2025)**: crescimento líquido de **141.949,02 ha (96,96%)**. Esse valor não é igual ao total bruto convertido: entradas e saídas da classe urbana são contabilizadas separadamente.

[41 anos de área urbana](reports/geourban_w001/rs_urban_series.csv) · [Transições por período](reports/geourban_w001/rs_urban_transitions.csv) · [Origens em 1985 das áreas urbanas em 2025](reports/geourban_w001/rs_endpoint_origins.csv)

As áreas são publicadas pelo MapBiomas. O total estadual ainda não foi reconciliado com o processamento raster próprio. A origem entre extremos não é necessariamente a classe imediatamente anterior à urbanização. Não urbano não significa rural; não há inferência causal ou previsão.

## Reproduzir a etapa validada

PowerShell, dentro deste repositório (o diretório mantém o nome geoflood-rs para preservar o trabalho):

```powershell
# O ambiente existente já está pronto. Para preparar outro ambiente:
python -m venv .venv
python -m pip --python .venv install -r requirements-geourban.lock.txt

.\.venv\Scripts\python.exe -m src.acquire
.\.venv\Scripts\python.exe -m src.official_tables
.\.venv\Scripts\python.exe -m src.boundaries
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Python 3.14.5; dependências fixadas. A aquisição baixa somente tabela, legenda e limites IBGE, cerca de 27,5 MB. Hashes fixos impedem troca silenciosa da fonte. O cache fica em data/raw/geourban_w001, ignorado pelo Git. Os testes essenciais GeoUrban podem ser executados sem baixar os dados.

## Validação espacial

Porto Alegre: área urbana de 13.653,36 ha em 1985 para 19.156,86 ha em 2025 (+40,31%). Primeira entrada urbana após 1985: 5.749,11 ha. A malha inteira está contida na grade exportada e nenhum pixel municipal foi excluído por lacuna temporal. Essas verificações avaliam consistência do processamento, não a acurácia temática do MapBiomas.

O pipeline distingue primeira conversão, reentrada e saldo líquido. O domínio comum exclui pixels sem classe conhecida em qualquer um dos 41 anos. Isso pode reduzir a cobertura; quantifique essa exclusão antes de aceitar resultados estaduais.

O acesso aos rasters exige projeto Earth Engine habilitado. No script `scripts/geourban_gee_statewide.js`, ajuste o asset da malha IBGE no seu projeto. As três exportações produzem séries municipais, origens e total estadual para reconciliação. A execução estadual ainda não foi validada de ponta a ponta.

## Qualidade e contribuição

```powershell
python -m pip --python .venv install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m unittest tests.test_geourban tests.test_urban_trajectory -q
```

O CI verifica lint, formatação e os oito testes GeoUrban independentes de dados locais. Os 36 testes do workspace, incluindo o legado, passaram localmente. Testes de aquisição e rasters precisam dos arquivos reais e não são substituídos por resultados simulados.

Use uma branch por alteração e descreva no PR o problema, o resultado, a validação e as limitações. A revisão humana antecede o merge. Credenciais, `.env`, rasters e dados brutos ficam fora do Git. O `.gitignore` não remove segredos que já tenham sido commitados.

## Método previsto para o P0

- Série única da Coleção 11, 1985–2025; classe urbana 24.
- Separar estoque anual, crescimento líquido, entradas brutas e primeira conversão. Não somar entradas anuais como se fossem pixels únicos.
- Classe anterior à primeira conversão exige trajetória raster. Origem entre extremos é outra métrica.
- Grupo agropecuário conforme legenda, mantendo agricultura, pastagem, silvicultura e mosaico separados.
- Limites IBGE 2024 fixos para comparabilidade; 497 municípios, com duas áreas operacionais de lagoas separadas.
- Cálculo em projeção equivalente adequada ao RS. Reconciliar municípios e áreas operacionais com o total raster.
- Rankings absoluto e proporcional, explicitando denominador e tratando base urbana zero como crescimento percentual indefinido.

## Escopo

O objetivo é produzir séries, conversões por origem, rankings absoluto e proporcional e mapas para os 497 municípios. Não urbano não significa rural. O produto não faz previsão nem afirma causalidade.

A malha IBGE 2024 é mantida fixa em 1985–2025: os resultados descrevem a evolução dentro desses territórios, não as divisas históricas de cada ano. Duas áreas operacionais de lagoas entram na reconciliação estadual e ficam fora dos rankings.

Documentos operacionais e o código legado GeoFlood são preservados no workspace, fora do conjunto inicial de publicação. A publicação inicial foca o pipeline GeoUrban, seus testes, fontes e resultados verificáveis.

## Fontes

Projeto MapBiomas — Coleção 11 da Série Anual de Mapas de Cobertura e Uso da Terra do Brasil, acesso em 11/11/2026: https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/ . A planilha autoriza uso público e gratuito mediante referência. Links e hashes em reports/geourban_w001/sources_manifest.json.

IBGE — Malha Municipal Digital 2024, RS, SIRGAS 2000: https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2024/UFs/RS/ . Datas e classes referem-se às versões registradas, não a uma verdade perfeita sobre ocupação física.
