# importa as bibliotecas necessarias para o projeto
from typing import List, Optional
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select


### CLASSES DO BD ###

# tabela de modalidades
class Modalidade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    descricao: str = Field(default="")
    
    # relacao 1:N
    atletas: List["Atleta"] = Relationship(back_populates="modalidade")
    imagem_url: str = Field(default="")

# tabela de atletas
class Atleta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    imagem_url: str = Field(default="")
    descricao:  str = Field(default="")
   
    # chave estrangeira da tabela modalidade
    modalidade_id: Optional[int] = Field(default=None, foreign_key="modalidade.id")
   
    # relacao de volta apontando para a classe pai
    modalidade: Optional[Modalidade] = Relationship(back_populates="atletas")



### CONFIGURACAO DO BANCO SQLITE ###

# define os parametros da criacao do arquivo de armazenamento
sqlite_file_name = "sinuca.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# cria o motor do banco configurado para rodar na thread atual
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def cria_bd_tabelas():
    SQLModel.metadata.create_all(engine)

# lida com o ciclo de vida da sessao no banco
def get_session():
    with Session(engine) as session:
        yield session



### CONFIGURACAO DO FASTAPI ###

# instancia principal da api
app = FastAPI()

# pastas internas para servir estaticos e htmls
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup():
    cria_bd_tabelas()




### ROTAS DE PAGINAS COMPLETAS ###

# mapeamento da pagina raiz das modalidades
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session: Session = Depends(get_session)):

    # resgata a lista global pelo select do sqlmodel
    modalidades = session.exec(select(Modalidade)).all()
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"modalidades": modalidades}
    )

# mapeamento da rota da pagina dos atletas
@app.get("/atletas.html", response_class=HTMLResponse)
async def pagina_atletas(request: Request, session: Session = Depends(get_session)):
    
    
    atletas = session.exec(select(Atleta)).all()
    return templates.TemplateResponse(
        request=request, 
        name="atletas.html", 
        context={"atletas": atletas}
    )


# ### ROTAS DE FORMULARIOS HTMX ###

# distribui o arquivo zerado para injecao no painel html
@app.get("/form-novo-atleta", response_class=HTMLResponse)
async def form_novo_atleta(request: Request):
    return templates.TemplateResponse(request=request, name="fragmentos/form_atleta.html", context={})

# procura e distribui o form preenchido baseado na id recebida via request
@app.get("/atletas/{atleta_id}/edit", response_class=HTMLResponse)
async def form_editar_atleta(request: Request, atleta_id: int, session: Session = Depends(get_session)):
    atleta = session.get(Atleta, atleta_id)
    return templates.TemplateResponse(request=request, name="fragmentos/form_edit_atleta.html", context={"atleta": atleta})


### MODALIDADES ###

# disponibiliza a caixa de forms da modalidade
@app.get("/form-nova-modalidade", response_class=HTMLResponse)
async def form_nova_modalidade(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/form_modalidade.html", 
        context={}
    )

@app.post("/modalidades", response_class=HTMLResponse)
async def criar_modalidade(
    request: Request, 
    nome: str = Form(...), 
    descricao: str = Form(""),
    imagem_url: str = Form(""),
    session: Session = Depends(get_session)
):

    nova_modalidade = Modalidade(nome=nome, descricao=descricao, imagem_url=imagem_url)
    session.add(nova_modalidade)
    session.commit()
    session.refresh(nova_modalidade)
    
    # cospe um unico card modificado ao invez de renderizar a pagina toda
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/card_modalidade.html", 
        context={"modalidade": nova_modalidade}
    )

# intercepta os cliques rapidos da barra de busca
@app.get("/buscar-modalidade", response_class=HTMLResponse)
async def buscar_modalidade(request: Request, q: str = "", session: Session = Depends(get_session)):

    if q:
        statement = select(Modalidade).where(Modalidade.nome.contains(q))
        modalidades = session.exec(statement).all()

    # desativa o filtro quando o form volta ao nulo
    else:
        modalidades = session.exec(select(Modalidade)).all()
        
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/lista_modalidades.html", 
        context={"modalidades": modalidades}
    )

# varre o banco local e deleta
@app.delete("/modalidades/{modalidade_id}")
async def deletar_modalidade(modalidade_id: int, session: Session = Depends(get_session)):
    modalidade = session.get(Modalidade, modalidade_id)
    if modalidade:
        session.delete(modalidade)
        session.commit()
    return ""


### ATLETAS ###

# captura payload do metodo post da guia de criacao manual
@app.post("/atletas", response_class=HTMLResponse)
async def criar_atleta(
    request: Request, 
    nome: str = Form(...), 
    imagem_url: str = Form(""), 
    descricao: str = Form(""),
    modalidade_id: int = Form(1), 
    session: Session = Depends(get_session)
):
    # estrutura de insercao similar a padronagem modalidade
    novo_atleta = Atleta(nome=nome, imagem_url=imagem_url, descricao=descricao, modalidade_id=modalidade_id)
    session.add(novo_atleta)
    session.commit()
    session.refresh(novo_atleta)
    
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/card_atleta.html", 
        context={"atleta": novo_atleta}
    )

# controla a indexacao via barra no front end
@app.get("/buscar-atleta", response_class=HTMLResponse)
async def buscar_atleta(request: Request, q: str = "", session: Session = Depends(get_session)):
    if q:
        statement = select(Atleta).where(Atleta.nome.contains(q))
        atletas = session.exec(statement).all()
    else:
        atletas = session.exec(select(Atleta)).all()
        
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/lista_atletas.html", 
        context={"atletas": atletas}
    )

# aplica os blocos atualizados via put htmx 
@app.put("/atletas/{atleta_id}", response_class=HTMLResponse)
async def atualizar_atleta(
    request: Request, 
    atleta_id: int, 
    nome: str = Form(...),
    descricao: str = Form(""), 
    session: Session = Depends(get_session)
):
    # faz um select e assina os novos conteudos antes de disparar pro banco
    atleta = session.get(Atleta, atleta_id)
    if atleta:
        atleta.nome = nome
        atleta.descricao = descricao
        session.add(atleta)
        session.commit()
        session.refresh(atleta)
        
    return templates.TemplateResponse(
        request=request, 
        name="fragmentos/card_atleta.html", 
        context={"atleta": atleta}
    )

# deleta card individual e devolve um padrao vazio htmx
@app.delete("/atletas/{atleta_id}")
async def deletar_atleta(atleta_id: int, session: Session = Depends(get_session)):
    atleta = session.get(Atleta, atleta_id)
    if atleta:
        session.delete(atleta)
        session.commit()
        
    return ""