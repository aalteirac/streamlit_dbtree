sed -i '' "/#begin/,/#end/c\ 
    #begin \
    version="$1", \
    #end
" setup.py 
git add .
git commit -m "auto-release"
git push
gh release create v0.2.2 -p --notes "bugfix release"
