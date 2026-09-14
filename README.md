# Alexa AI Bridge

Uma Alexa Custom Skill em pt-BR que usa AWS Lambda e a OpenAI Responses API para transformar uma Echo Dot em interface de voz para um assistente conversacional. O MVP não tem memória entre sessões ou integrações com contas; cada resposta usa busca web da OpenAI para reduzir respostas factuais sem fonte.

## Arquitetura

`Echo Dot → Alexa → Custom Skill → AWS Lambda → OpenAI Responses API → Lambda → Alexa`

A cada sessão, o Lambda guarda `previous_response_id` em `sessionAttributes`. A pergunta seguinte envia esse ID para a Responses API, preservando o contexto apenas enquanto a sessão Alexa está aberta.

## Requisitos

- Python 3.11+
- Conta AWS com acesso a Lambda e CloudWatch
- Conta Alexa Developer
- Conta OpenAI API com faturamento próprio (a assinatura ChatGPT não é crédito de API)
- Git e, opcionalmente, GitHub CLI

## Nome e conversa

O nome de invocação é `meu assistente`. Use `Alexa, abrir meu assistente`, aguarde `Pode falar.` e faça perguntas consecutivas sem repetir o nome enquanto a sessão estiver ativa. Cada resposta usa `shouldEndSession=false` e uma reprompt curta; `parar` e `cancelar` encerram.

O nome é adequado para desenvolvimento, mas a validação final de disponibilidade e reconhecimento é feita pela Alexa Developer Console e pela Echo. A Amazon pode rejeitar nomes genéricos em certificação pública.

## Configuração local

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
pytest
```

Preencha `.env` somente no seu computador. Nunca cole a chave no chat, em código ou no Git:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
ALEXA_SKILL_ID=
```

Os testes não chamam a OpenAI real; usam doubles/mocks.

## OpenAI

Crie uma conta da API separada, se desejar: entre em [platform.openai.com](https://platform.openai.com/), configure billing, crie o Project `alexa-ai-bridge`, defina orçamento/limites e gere uma chave apenas para esse projeto. Desative recarga automática inicialmente, se essa opção estiver disponível. Guarde a chave em um cofre de senhas; não a envie a ninguém.

`OPENAI_MODEL` permite trocar o modelo sem alterar código. O padrão `gpt-5.6-luna` usa `reasoning.effort: none` e baixa verbosidade para respostas vocais curtas. Consulte a [documentação do modelo](https://developers.openai.com/api/docs/models/gpt-5.6-luna) e os [preços atuais](https://platform.openai.com/pricing), pois valores e disponibilidade podem mudar.

## Lambda e deploy

1. Execute `./scripts/build_lambda.sh`. O resultado será `dist/alexa-ai-bridge.zip`; ele não contém `.env` ou testes.
2. No AWS Console, escolha uma região próxima e crie uma função Lambda Python 3.13 chamada `alexa-ai-bridge`.
3. Envie o ZIP e configure o handler como `src.lambda_function.lambda_handler`.
4. Configure timeout de 10 segundos e memória de 1024 MB para reduzir o tempo de inicialização e obter mais CPU. A chamada OpenAI (incluindo busca web obrigatória) tem timeout próprio de 7 segundos e sem retentativas automáticas. Um deadline Linux de 7,2 segundos cobre toda a invocação, inclusive criação do client e resolução DNS; ao excedê-lo, preserva a sessão e retorna um erro amigável. O limite também respeita o tempo restante informado pela Lambda. Isso limita o tempo de espera, mas não garante que a API externa responderá a tempo em toda pergunta.
5. Em **Configuration → Environment variables**, adicione `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-5.6-luna` e, depois de criada a Skill, `ALEXA_SKILL_ID`. Use a criptografia padrão da Lambda com KMS e restrinja quem pode ver/alterar configuração da função. Para uma equipe ou produção mais sensível, migre a chave para AWS Secrets Manager com uma policy IAM de leitura exclusiva.
6. Em **Monitor**, consulte CloudWatch Logs. Os logs registram IDs/tipos, modelo, latência e categoria de erro, nunca o texto completo ou segredos.

## Alexa Skill

1. Abra [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).
2. Selecione **Create Skill**: nome exibido `Alexa AI Bridge`, idioma **Portuguese (BR)** e modelo **Custom**.
3. Em **Build → Interaction Model → JSON Editor**, substitua pelo conteúdo de `alexa/interaction_model_pt_BR.json`; salve e use **Build Model**.
4. Copie o Skill ID para `ALEXA_SKILL_ID` na Lambda (nunca para este README) e configure o endpoint como ARN da função Lambda na mesma região suportada.
5. Em **Test**, habilite Development e teste primeiro pelo simulador; depois habilite a Skill na mesma conta Amazon da Echo Dot e faça o teste físico.

## Fluxo de validação

1. Rode `pytest` localmente.
2. Faça uma chamada OpenAI isolada só depois de configurar uma chave local.
3. Teste a função no Lambda.
4. Teste pelo simulador Alexa.
5. Teste na Echo: pergunte sobre Albert Einstein, depois `Quando ele nasceu?` e `Em qual país?`. Confirme no CloudWatch que três chamadas ocorreram e que os dois follow-ups receberam contexto.

## GitHub

O repositório deve ser privado. Após autenticar o GitHub CLI, crie `gxbreus/alexa-ai-bridge` como privado, adicione `origin` e envie os commits. Confirme `git status` e revise que `.env` não aparece antes de cada commit.

## Troubleshooting

- **Alexa encerra após resposta:** confirme que existe reprompt e que `shouldEndSession` é `false`.
- **Resposta amigável de erro:** verifique CloudWatch para a categoria sem expor logs ao usuário.
- **Falha de autenticação/saldo:** valide a chave, billing, projeto e budget no OpenAI Platform.
- **Nome não reconhecido:** teste no simulador e revise o histórico da Alexa App; talvez seja necessário um nome mais distintivo.

## Segurança e roadmap

Não versione chaves, ZIPs, `.env` ou logs contendo dados sensíveis. A busca web é obrigatória e pode elevar o consumo de API; acompanhe o Usage Dashboard por projeto. Ela reduz alucinações, mas não transforma fontes da internet em verdade absoluta. Calendar, Gmail, memória persistente e Home Assistant ficam para milestones posteriores e exigirão desenho de permissões/confirmação.
