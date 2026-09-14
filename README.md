# Alexa AI Bridge

Uma ponte entre uma Amazon Echo e a OpenAI: você abre uma Skill, faz uma pergunta e recebe uma resposta em voz alta, com contexto durante a sessão e busca web antes de cada resposta.

O projeto nasceu da vontade de aproveitar uma Echo Dot de 3ª geração como interface para um assistente pessoal. Usa os caminhos oficiais da Alexa, sem modificar o firmware do aparelho e sem depender de um computador ligado o tempo todo.

É um projeto independente, sem vínculo com Amazon ou OpenAI. Compartilhar o código não publica a Skill na loja da Alexa: cada pessoa precisa configurar suas próprias contas, função Lambda e Skill.

## Funcionalidades e experiência de voz

- Perguntas e respostas em português brasileiro.
- OpenAI Responses API com busca web obrigatória.
- Instruções para priorizar fontes confiáveis e reconhecer quando não consegue confirmar um dado.
- Contexto enquanto a sessão Alexa estiver aberta.
- Respostas curtas para voz, com remoção de URLs na saída falada.
- Sessão mantida aberta com reprompt e saída por `parar` ou `cancelar`.
- Tratamento de falhas da API e demora excessiva.

**Limitação importante:** esta versão exige frases-guia como `me diga`, `pergunte`, `quero saber`, `explique` ou `responda`. Você não precisa repetir o nome da Skill dentro da sessão, mas precisa usar uma dessas frases para que a Alexa reconheça a pergunta. Não é uma interface de transcrição livre.

O slot `AMAZON.SearchQuery` exige uma frase-guia nos exemplos do intent, conforme a [documentação da Amazon](https://developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html). A captura de respostas por diálogo tem regras diferentes e não está implementada aqui.

## Arquitetura e funcionamento

```mermaid
flowchart LR
    Echo[Echo Dot] --> Alexa[Alexa / Custom Skill]
    Alexa --> Lambda[AWS Lambda / Python]
    Lambda --> API[OpenAI Responses API]
    API --> Search[Busca web]
    Search --> API
    API --> Lambda
    Lambda --> Alexa
    Alexa --> Echo
```

1. `Alexa, abrir meu assistente` gera um `LaunchRequest`. A Lambda responde `Pode falar.`.
2. Uma frase como `me diga o que é arquitetura serverless` aciona o intent `AskAIIntent`. A Alexa coloca a pergunta no slot `query`.
3. O backend envia esse conteúdo pelo SDK oficial da OpenAI, com a ferramenta `web_search`, contexto de busca `low` e `tool_choice=required`. O modelo precisa usar a ferramenta antes de responder.
4. As instruções orientam respostas curtas em português, fundamentadas nos resultados consultados. A avaliação da qualidade das fontes é feita pelo modelo; não há verificador independente das afirmações. Busca web reduz respostas sem fundamento, mas não garante ausência de erros.
5. A Lambda prepara o texto para voz e devolve a resposta. `shouldEndSession=false` e a reprompt `Pode falar.` permitem continuar.
6. O ID retornado fica em `sessionAttributes.previous_response_id`. A próxima pergunta envia esse ID à API para manter o contexto, e reaplica as instruções do assistente.

Não há banco de dados ou memória persistente própria. As respostas são mantidas pela Responses API conforme as políticas do provedor. Encerrar a sessão remove o contexto disponível à Skill, mas não equivale a apagar dados dos provedores.

### Organização do código

| Arquivo | Responsabilidade |
| --- | --- |
| `src/lambda_function.py` | Entrada da Lambda, handlers e limite total de tempo. |
| `src/alexa_handlers.py` | Abertura, perguntas, ajuda, saída e reconhecimento. |
| `src/openai_service.py` | Client OpenAI, busca, contexto e falhas da API. |
| `src/prompts.py` | Instruções de idioma, voz e uso de fontes. |
| `src/config.py` | Variáveis de ambiente. |
| `src/deadline.py` | Interrupção da invocação com sinais Linux. |
| `alexa/interaction_model_pt_BR.json` | Modelo de interação para importar na console Alexa. |
| `scripts/build_lambda.sh` | Empacotamento do código e dependências. |
| `tests/` | Testes com mocks, sem chamadas faturáveis. |

## Clonar e configurar

São necessários Git, Python, conta AWS, conta Amazon Developer e conta OpenAI API com faturamento/saldo. A assinatura do ChatGPT não substitui o faturamento da API.

Para reproduzir o pacote descrito aqui, use **Linux x86_64 com Python 3.13**, Bash e `zip`. O script inclui bibliotecas nativas do ambiente de build; um ZIP gerado no macOS ou Windows não é compatível automaticamente com a Lambda.

```bash
git clone https://github.com/gxbreus/alexa-ai-bridge.git
cd alexa-ai-bridge
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install 'pytest>=8,<9'
cp .env.example .env
pytest -q
```

Preencha seu `.env` local:

```dotenv
OPENAI_API_KEY=sua_chave_da_api
OPENAI_MODEL=gpt-5.6-luna
ALEXA_SKILL_ID=
```

| Variável | Uso |
| --- | --- |
| `OPENAI_API_KEY` | Obrigatória. Chave do seu projeto OpenAI, usada no backend. |
| `OPENAI_MODEL` | Padrão: `gpt-5.6-luna`. O modelo precisa estar liberado na sua conta e aceitar busca web, `reasoning.effort=none` e baixa verbosidade. |
| `OPENAI_TIMEOUT_SECONDS` | Opcional. Padrão: `7`. Timeout do SDK; a invocação também tem um deadline total. |
| `ALEXA_SKILL_ID` | Opcional nesta versão. É lida pela configuração, mas não valida requisições no código. A autorização por Skill ID é configurada no gatilho Alexa Skills Kit da AWS. |

O `.env` é ignorado pelo Git e não entra no ZIP. Na Lambda, configure as variáveis pela AWS: editar o `.env` local não altera a função publicada.

### OpenAI

1. Acesse a [OpenAI Platform](https://platform.openai.com/), crie um projeto e configure o faturamento da API.
2. Gere uma chave para esse projeto. Use suas próprias credenciais no `.env` e na Lambda.
3. Libere o modelo escolhido em `OPENAI_MODEL`. Disponibilidade e limites podem variar por conta.
4. Acompanhe [Usage](https://platform.openai.com/usage), filtrando pelo projeto, e consulte os [preços atuais](https://developers.openai.com/api/docs/pricing), inclusive os da busca web.

Referência da integração: [busca web na Responses API](https://developers.openai.com/api/docs/guides/tools-web-search).

## Backend na AWS Lambda

Com o ambiente virtual ativo e Python 3.13 disponível como `python3`:

```bash
./scripts/build_lambda.sh
```

O resultado é `dist/alexa-ai-bridge.zip`. O script substitui o ZIP anterior e reconstrói `build/lambda/`, incluindo dependências e `src/`, sem o `.env` ou os testes do projeto.

No console AWS:

1. Selecione **us-east-1 / Norte da Virgínia** e crie uma função **do zero**, chamada `alexa-ai-bridge`.
2. Use runtime **Python 3.13**, arquitetura **x86_64** e perfil de execução com permissão para CloudWatch Logs.
3. Na aba **Código**, envie o ZIP pelo menu de atualização de código.
4. Em **Configurações do runtime**, defina o manipulador como `src.lambda_function.lambda_handler`.
5. Em **Configuração geral**, use memória de **1024 MB** e timeout de **10 segundos**.
6. Em **Variáveis de ambiente**, configure sua `OPENAI_API_KEY` e `OPENAI_MODEL`. Se definir `OPENAI_TIMEOUT_SECONDS`, use `7` para reproduzir esta configuração.

A função precisa alcançar a API OpenAI pela internet. Neste exemplo, não a conecte a uma VPC privada sem saída de rede configurada.

O código aplica um deadline total de **7,2 segundos**, respeita o tempo restante da Lambda e desativa retentativas automáticas. Pesquisa e inicializações frias podem ultrapassar a janela de resposta da Alexa. Mais memória fornece mais CPU à Lambda, mas não acelera a pesquisa no provedor externo; confirme o tempo no simulador e no aparelho.

## Configurar sua Alexa Skill

1. Abra a [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) com a mesma conta Amazon vinculada à Echo.
2. Clique em **Create Skill**. Nome: `Meu Assistente`; idioma: **Portuguese (BR)**.
3. Escolha **Other**, modelo **Custom**, hospedagem **Provision your own** e template **Start from Scratch**.
4. Em **Build → Interaction Model → JSON Editor**, importe ou cole `alexa/interaction_model_pt_BR.json`. Salve e execute o build.
5. Em **Endpoint**, copie **Your Skill ID**. Na Lambda, clique em **Adicionar gatilho**, selecione **Alexa Skills Kit** e restrinja o gatilho ao ID da sua Skill. Mantenha a verificação de Skill ID habilitada no gatilho.
6. Volte ao endpoint da Skill, selecione **AWS Lambda ARN** e substitua a ARN do template em **Default Region (Required)** pela ARN da sua função. Os campos opcionais podem ficar vazios neste exemplo. Salve.
7. Na aba **Test**, habilite **Development**, selecione português brasileiro e teste pelo **Alexa Simulator**.
8. Teste na Echo vinculada à mesma conta. Para uso em desenvolvimento na sua conta, não é necessário publicar a Skill na loja.

O nome de invocação é `meu assistente` e pode ser alterado no JSON ou na console. O reconhecimento no aparelho e eventual certificação precisam ser testados. Clonar o repositório não dá acesso à implantação do autor: crie seus próprios recursos e credenciais.

## Exemplos de conversa

Estas falas são sugestões de teste, não transcrições de respostas garantidas. Aguarde cada resposta e continue enquanto a sessão estiver ativa.

### Arquitetura e contexto

```text
Alexa, abrir meu assistente
Me diga o que é arquitetura serverless em duas frases
Explique a principal vantagem dela
Me diga uma limitação desse modelo
Parar
```

Os pedidos seguintes devem continuar o assunto de arquitetura serverless. A sequência demonstra contexto sem depender de uma notícia que pode mudar.

### Design e acessibilidade

```text
Alexa, abrir meu assistente
Me diga a diferença entre UX e UI de forma simples
Explique como elas se complementam
Me diga um exemplo de acessibilidade em um formulário
Cancelar
```

### Pesquisa factual

```text
Alexa, abrir meu assistente
Pergunte quem foi o vice-artilheiro do Campeonato Brasileiro de 2003
Me diga por qual clube ele jogava
Responda quantos gols ele marcou naquela edição
Parar
```

Use a sequência para avaliar pesquisa e contexto com um dado histórico. Confira as respostas em fonte independente antes de usá-las como referência ou publicar uma demonstração.

## Testes e diagnóstico

```bash
source .venv/bin/activate
pytest -q
```

Os testes cobrem sessão, contexto entre turnos, pergunta vazia, falhas da API, saída de links para voz e deadline. Não comprovam a qualidade factual do modelo nem substituem testes de rede, reconhecimento de fala e tempo de resposta na Echo.

Abra **Monitor → CloudWatch Logs** na AWS. Os logs de aplicação registram modelo, latência, IDs/tipos de requisição e categoria de falha, sem registrar intencionalmente a chave ou o texto completo das perguntas.

| Sintoma | O que conferir |
| --- | --- |
| Endpoint não salva / gatilho inválido | Gatilho Alexa Skills Kit, Skill ID autorizado e ARN correta em Default Region. |
| Pergunta não chega à função | Frase-guia, idioma pt-BR, slot `query` e build do modelo. |
| Mensagem genérica de falha | Categoria no CloudWatch; chave, saldo, acesso ao modelo e rede. |
| Timeout | Configuração, inicialização fria e latência da API/busca. Aumentar só o timeout da Lambda não amplia a janela da Alexa. |
| Contexto desaparece | Sessão encerrada por saída ou inatividade; não há memória entre sessões. |
| Echo não encontra a Skill | Testing em Development, conta Amazon e nome de invocação. |

## Custos, privacidade e próximos passos

Executar o projeto usa serviços de terceiros: OpenAI (modelo e busca web) e AWS (Lambda e logs). Créditos e franquias variam por conta. Consulte [Usage da OpenAI](https://platform.openai.com/usage) e [Billing da AWS](https://console.aws.amazon.com/costmanagement/).

As falas são processadas pela Alexa e o conteúdo reconhecido no slot é enviado à OpenAI. A busca obrigatória também pode usar informações da pergunta em consultas de pesquisa. Evite informações pessoais sensíveis na demonstração.

Não publique `.env`, chaves, credenciais AWS ou capturas que revelem segredos. Use suas próprias contas e nunca coloque a chave OpenAI no modelo de interação ou no código versionado.

Possíveis evoluções: captura em diálogo, tratamento mais completo de citações, avaliações de qualidade factual e otimização de latência. Memória persistente, calendário e automações pessoais exigem novos fluxos de autorização e não fazem parte da versão atual.
