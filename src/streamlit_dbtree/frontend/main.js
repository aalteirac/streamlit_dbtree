
var r = document.querySelector(':root');

function setCSSVar(varn,val) {
  r.style.setProperty(varn, val);
}

function sendValue(value) {
  Streamlit.setComponentValue(value)
}

function listenSel(){
  $('.jstree').on('changed.jstree', function (e, data) {
    var i, j, r = [];
    for(i = 0, j = data.selected.length; i < j; i++) {
      r.push( {id:data.instance.get_node(data.selected[i]).id, type:data.instance.get_node(data.selected[i]).data });
    }
    sendValue(r)
  })
}
async function onRender(event) {
  const {data,backgroundColor,fontColor,height,selectColor } = event.detail.args;
  if (!window.rendered) {
    Streamlit.setFrameHeight(height+20);
    setCSSVar("--selnode",selectColor)
    setCSSVar("--fontcolor",fontColor)
    document.getElementById("root").style.backgroundColor=backgroundColor;
    document.getElementById("root").style.height=`${height}px`;
    var datajs=[]
    await JSON.parse(data).map(async (el)=>{
      datajs.push({"icon":"dbicon","id":el.name,"parent":"#","text":el.name,data:"DATABASE"})
      await el.schema.map(async(sc)=>{
        datajs.push({"icon":"schema","id":el.name+'.'+sc.name,"parent":`${el.name}`,"text":sc.name,data:"SCHEMA"})
        await sc.tables.map((tb)=>{
          datajs.push({"icon":"table","id":el.name+'.'+sc.name+'.'+tb.name,"parent":el.name+'.'+sc.name,"text":tb.name,data:"TABLE"})
        }) 
        await sc.views.map((tb)=>{
          datajs.push({"icon":"view","id":el.name+'.'+sc.name+'.'+tb.name,"parent":el.name+'.'+sc.name,"text":tb.name,data:"VIEW"})
        }) 
      }) 
    })
    $('#root').jstree({ 'core' : {
        "themes" : {
          "dots" : false
        },
        'data' : datajs
    } });
    setTimeout(() => {
      listenSel()
    }, 1000);
    window.rendered = true
  }
}


Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender)

Streamlit.setComponentReady()


