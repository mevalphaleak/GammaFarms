const signPermitWithMetamask = async ({
  provider,
  name,
  version,
  chainId,
  verifyingContract,
  owner,
  spender,
  nonce,
  deadline,
  value
}) => {
  const messageData = await createPermitMessageData({
    name, version, chainId, verifyingContract, owner, spender, nonce, deadline, value
  })
  const sig = await signDataWithMetamask(provider, owner, JSON.stringify(messageData.typedData));
  return Object.assign({}, sig, messageData.message);
}

const signDataWithMetamask = async (provider, owner, typeData) => {
  const signature = await provider.send('eth_signTypedData_v4', [owner, typeData]);
  const r = signature.slice(0, 66);
  const s = '0x' + signature.slice(66, 130);
  const v = 27 + Number('0x' + signature.slice(130, 132)) % 27;
  return {v, r, s}
}

const createPermitMessageData = async ({
  name,
  version,
  chainId,
  verifyingContract,
  owner,
  spender,
  nonce,
  deadline,
  value
}) => {
  const message = {
    owner,
    spender,
    nonce: nonce.toString(),
    deadline: deadline.toString(),
    value: value.toString()
  }
  const typedData = {
    types: {
      EIP712Domain: [
        {
          name: 'name',
          type: 'string'
        },
        {
          name: 'version',
          type: 'string'
        },
        {
          name: 'chainId',
          type: 'uint256'
        },
        {
          name: 'verifyingContract',
          type: 'address'
        }
      ],
      Permit: [
        {
          name: 'owner',
          type: 'address'
        },
        {
          name: 'spender',
          type: 'address'
        },
        {
          name: 'value',
          type: 'uint256'
        },
        {
          name: 'nonce',
          type: 'uint256'
        },
        {
          name: 'deadline',
          type: 'uint256'
        }
      ]
    },
    primaryType: 'Permit',
    domain: {name, version, chainId, verifyingContract},
    message: message
  }

  return {
    typedData,
    message
  }
}

export { signPermitWithMetamask };
