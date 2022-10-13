# streamlit-dbtree

Visualize Snowflake DB tree

## Installation instructions 

```sh
pip install streamlit-dbtree
```

## Usage instructions

```python
import streamlit as st

from streamlit_dbtree import streamlit_dbtree

ctx = snowflake.connector.connect(
    user='<user_name>',
    password='<password>'',
    account='<account_locator>'
    )   
value = streamlit_dbtree(ctx,key="mysnownav")
if value is not None:
    for sel in value:
        st.write(sel.get("id") +" IS A " +sel.get("type"))

```
## Options
    Show the border or not:
    showBorder=<bool>
    
    Tree height:
    height=<int>

    Tree background color:
    backgroundColor=<str> HEX value or str color like "red", "blue"

    Tree font color:
    fontColor=<str> HEX value or str color like "red", "blue"

    Tree background color for selected item(s):
    selectColor=<str> HEX value or str color like "red", "blue"
    
    Tree background color for hovered item(s):
    hoverColor=<str> HEX value or str color like "red", "blue"

