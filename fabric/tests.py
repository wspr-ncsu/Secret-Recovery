import json
from skrecovery import sigma, helpers
from fabric import ledger, transaction, block as ledgerBlock

def create_tx():
    sk, vk = sigma.keygen()
    proposal: dict = {'key': 'hello world!'}
    vk_str: str = sigma.stringify(vk)
    signature: sigma.Signature = sigma.sign(sk, proposal)
    tx_signature: transaction.Signer = transaction.Signer(vk_str, signature)
    tx: transaction.Transaction = ledger.post(transaction.TxType.FAKE.value, proposal, tx_signature)
    return tx

def test_ledger_post():
    tx: transaction.Transaction = create_tx()
    txstr = tx.to_string()

def test_tx_serialization():
    tx1 = create_tx()
    tx1str = tx1.to_string()
    tx2 = transaction.Transaction.from_dict(json.loads(tx1str))
    tx2str = tx2.to_string()
    assert tx1str == tx2str
    
def test_block_serialization():
    block: ledgerBlock.Block = ledgerBlock.Block()
    tx = create_tx()
    block.data.add_tx(tx.to_string())
    block.metadata.bitmap = {'hello': 'world'}
    bdict = block.to_dict()
    bdict2: ledgerBlock.Block = ledgerBlock.Block.from_dict(bdict)
    bdict2 = bdict2.to_dict()
    print(bdict)
    print('-'*80)
    print(bdict2)
    assert bdict == bdict2
    

if __name__ == '__main__':
    test_tx_serialization()