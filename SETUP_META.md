# Configuração da Meta para publicar via Instagram Graph API

A Content Publishing API **não funciona em conta pessoal comum**. O caminho é
converter sua conta pessoal em conta Profissional (ela continua sendo "sua",
com o mesmo @ e seguidores) e vinculá-la a uma Página do Facebook.

## 1. Converter a conta para Profissional

1. App do Instagram → Perfil → menu → **Configurações e privacidade** →
   **Tipo de conta e ferramentas** → **Mudar para conta profissional**.
2. Escolha **Criador** ou **Empresa** — ambos funcionam com a API. Para conta
   pessoal de conteúdo, "Criador" costuma ser o mais adequado.

## 2. Criar/vincular uma Página do Facebook

1. Crie uma Página no Facebook (pode ser mínima, sem publicações — ela serve
   apenas de "ponte" para a API).
2. No Instagram: **Configurações** → **Central de Contas** (ou "Página
   vinculada") → vincule a Página criada.
3. Confirme no Facebook, em Configurações da Página → **Contas vinculadas**,
   que o Instagram aparece conectado.

## 3. Criar o app na Meta for Developers

1. Acesse <https://developers.facebook.com> → **My Apps** → **Create App**.
2. Tipo: **Business**.
3. No painel do app, adicione os produtos **Facebook Login** e
   **Instagram Graph API**.
4. Enquanto o app estiver em **modo de desenvolvimento**, ele só publica em
   contas com papel no app (você, como admin). Para uso próprio isso é
   suficiente — **não precisa de App Review**.

## 4. Gerar o token de longa duração

1. Abra o **Graph API Explorer** (<https://developers.facebook.com/tools/explorer>).
2. Selecione seu app e gere um **User Token** com as permissões:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
3. O token gerado é de curta duração (~1h). Troque por um de **longa duração
   (~60 dias)**:

   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={APP_ID}
     &client_secret={APP_SECRET}
     &fb_exchange_token={TOKEN_CURTO}
   ```

4. Guarde o `access_token` retornado — é ele que vai no Secret
   `IG_ACCESS_TOKEN`.

## 5. Descobrir o IG_USER_ID

Com o token de longa duração:

```
GET https://graph.facebook.com/v21.0/me/accounts
→ anote o "id" da sua Página

GET https://graph.facebook.com/v21.0/{PAGE_ID}?fields=instagram_business_account
→ o campo instagram_business_account.id é o seu IG_USER_ID
```

## 6. Secrets no GitHub

No repositório: Settings → Secrets and variables → Actions:

| Secret | Valor |
|---|---|
| `IG_USER_ID` | ID obtido no passo 5 |
| `IG_ACCESS_TOKEN` | token de longa duração do passo 4 |

## 7. ⚠️ Expiração do token (~60 dias)

O token de longa duração **expira em ~60 dias** e a Meta não avisa. Como o
workflow roda 1×/mês, na prática você precisa renovar **a cada execução
alternada**. Duas formas de lidar:

**a) Renovação manual (simples).** Repita o passo 4 antes do dia 1 dos meses
pares/ímpares e atualize o Secret. Coloque um lembrete recorrente na agenda.

**b) Renovação automática (opcional).** O mesmo endpoint
`fb_exchange_token` aceita um token de longa duração ainda válido e devolve
um novo de 60 dias. Dá para adicionar um step no workflow que renova e grava
o Secret de volta via `gh secret set` — isso exige um **PAT** do GitHub com
escopo `repo` guardado como Secret (`GH_PAT`):

```yaml
- name: Renovar token da Meta
  env:
    GH_TOKEN: ${{ secrets.GH_PAT }}
  run: |
    NOVO=$(curl -s "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${{ secrets.META_APP_ID }}&client_secret=${{ secrets.META_APP_SECRET }}&fb_exchange_token=${{ secrets.IG_ACCESS_TOKEN }}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
    gh secret set IG_ACCESS_TOKEN --body "$NOVO" -R ${{ github.repository }}
```

Se um dia migrar o Instagram para um **Business Manager**, um token de
**System User** elimina a expiração — mas para conta pessoal/Creator o
esquema acima é o caminho.

## 8. Restrições da API que afetam este projeto

- As imagens precisam estar em **URL pública** e em **JPEG** (o renderizador
  já converte). Por isso o workflow commita os JPEGs e usa
  `raw.githubusercontent.com` → **o repositório precisa ser público**. Se
  preferir repositório privado, alternativas: publicar os JPEGs num branch
  `gh-pages` de um segundo repo público, ou num bucket/S3.
- Limite de 50 publicações via API por 24h (dois carrosséis/mês está longe
  disso).
- Carrossel: 2 a 10 itens (usamos 2 por carrossel).
