import json
from fabric.transaction import Transaction, Signer
from skrecovery import helpers, database, config

class BlockHeader:
    number: int = 0
    chainid: str = 'skrec'
    data_hash: str = None
    previous_hash: str = None
    
    def update_from_last_block(self, block: dict):
        if block and 'header' in block:
            self.previous_hash = block['header']['data_hash']
            self.number = int(block['header']['number']) + 1
    
    def to_dict(self):
        return {
            'number': self.number,
            'chainid': self.chainid,
            'data_hash': self.data_hash,
            'previous_hash': self.previous_hash
        }
        
    @staticmethod
    def from_dict(data: dict) -> 'BlockHeader':
        header = BlockHeader()
        header.number = int(data['number'])
        header.chainid = data['chainid']
        header.data_hash = data['data_hash']
        header.previous_hash = data['previous_hash']
        return header
        
class BlockData:
    transactions: list[Transaction] = []
    
    def __init__(self, transactions: list[Transaction] = []):
        self.transactions = transactions
        
    def add_tx(self, tx: dict | Transaction):
        tx: Transaction = Transaction.from_dict(tx) if isinstance(tx, dict) else tx
        self.transactions.append(tx)
        return tx.get_id()
        
    def reset(self):
        self.transactions = []
        
    def get_hash(self):
        return helpers.hash256(helpers.stringify(self.to_dict()))
    
    def to_dict(self):
        return [tx.to_dict() for tx in self.transactions]
    
    @staticmethod
    def from_dict(txs: dict):
        txs = [Transaction.from_dict(tx) for tx in txs]
        return BlockData(txs)
    
class BlockMetaData:
    bitmap: dict = None
    creator: Signer = None
    verifiers: list[Signer] = []
    last_config_block_number: int = 0
    
    def __init__(self, bitmap: dict = None, creator: Signer = None):
        self.bitmap, self.creator = bitmap, creator
        
    def to_dict(self) -> dict:
        creator = self.creator.to_dict() if self.creator else None
        return {
            'bitmap': self.bitmap, 
            'creator': creator,
            'verifiers': [v.to_dict() for v in self.verifiers],
            'last_config_block_number': self.last_config_block_number
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'BlockMetaData':
        creator = Signer.from_dict(data['creator']) if data['creator'] else None
        metadata: BlockMetaData = BlockMetaData(data['bitmap'], creator)
        metadata.verifiers = [Signer.from_dict(v) for v in data['verifiers']]
        metadata.last_config_block_number = data['last_config_block_number']
        return metadata
        
class Block:
    header: BlockHeader = None
    data: BlockData = None
    metadata: BlockMetaData = None
    
    def __init__(self, init=True) -> None:
        if init:
            self.header = BlockHeader()
            latest_block: dict = database.get_latest_block()
            self.header.update_from_last_block(latest_block)
            self.data = BlockData()
            self.metadata = BlockMetaData()
            
    def get_number(self):
        return self.header.number
        
    def set_data_hash(self):
        self.header.data_hash = self.data.get_hash()
        
    def get_signable_data(self):
        return {
            'data': self.data.to_dict(),
            'previous_hash': self.header.previous_hash,
        }
        
    def save(self):
        database.save_block(self.to_dict())
        
    def size(self):
        return len(helpers.stringify(self.to_dict()).encode('utf-8'))
        
    def verify(self):
        # verify creator signature
        if not self.metadata.creator.verify(self.get_signable_data()):
            print('Creator signature invalid')
            return False
        
        # verify verifiers signatures
        counter, quorom = 0, 2 * config.NUM_FAULTS + 1
        
        for verifier in self.metadata.verifiers:
            if verifier.verify(self.get_signable_data()):
                counter += 1

        return counter >= quorom
            
    def verify_previous_block(self, prev_block: 'Block'):
        return self.header.previous_hash == prev_block.header.data_hash
    
    def find_transaction_by_id(self, txid: str):
        for tx in self.data.transactions:
            if tx.get_id() == txid:
                return tx
        return None
    
    def to_dict(self):
        return {
            '_id': self.header.number,
            'chainid': self.header.chainid,
            'header': self.header.to_dict(),
            'data': self.data.to_dict(),
            'metadata': self.metadata.to_dict()
        }
        
    @staticmethod
    def from_dict(data: dict) -> 'Block':
        block: Block = Block(init=False)
        block.header = BlockHeader.from_dict(data['header'])
        block.data = BlockData.from_dict(data['data'])
        block.metadata = BlockMetaData.from_dict(data['metadata'])
        return block
        
    @staticmethod
    def from_number(number: int):
        data = database.find_block_by_number(number)
        return Block.from_dict(data)