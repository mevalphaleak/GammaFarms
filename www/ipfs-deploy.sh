# Build www:
yarn build
if [ $? != 0 ]
then
    echo "Build has failed, exiting..."
    exit 1
fi

# Clean existing IPFS data if any:
currently_pinned=$( ipfs pin ls --type recursive )
if [ ! -z "$currently_pinned" ]
then
    echo -e "\nRemoving existing files from IPFS node..."
    ipfs pin ls --type recursive | cut -d' ' -f1 | xargs -n1 ipfs pin rm
    ipfs repo gc
fi

# Move build to /var/www and add to IPFS:
echo -e "\nAdding new build files to IPFS node..."
rm -rf /var/www
cp -r build /var/www
ipfs add -r /var/www

# Show new link:
hash="$( ipfs pin ls --type recursive | cut -d' ' -f1 )"
echo -e "\n\nSuccessfully deployed new build: http://localhost:4000/ipfs/$hash"
