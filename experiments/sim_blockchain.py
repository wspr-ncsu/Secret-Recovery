import argparse, random, pickle
from skrecovery.client import Client
from skrecovery.server import Server
from skrecovery.helpers import Benchmark, startStopwatch, endStopwatch
from fabric.block import Block
from fabric.transaction import Transaction
from fabric import ledger
from fabric import noise_simulation
from experiments.misc import get_client, get_cloud
from experiments.store import main as store_script, client_secret_info
from fabric import ordering_service
from skrecovery import config, database

BLK_SEEDS = []
START_BLK_ID = -1
filename="seeded_blks.pkl"

def rand_block_data():
    return BLK_SEEDS[random.randint(0, len(BLK_SEEDS)-1)]

def init():
    global BLK_SEEDS
    # load seeded transactions from pickle file
    try:
        with open(filename, 'rb') as f:
            BLK_SEEDS = pickle.load(f)
    except Exception:
        print("Pickle file is empty or corrupted. Creating new seeded blocks.")
        BLK_SEEDS = []
        
    if BLK_SEEDS:
        return BLK_SEEDS
    else:
        print("Creating seeded blocks")
        for _ in range(config.T_CHAL):
            print("\rCreating block", _+1, end='')
            BLK_SEEDS.append(seed_transactions())
        print('')
        with open(filename, 'wb') as f:
            pickle.dump(BLK_SEEDS, f)

def seed_transactions(transactions: list[Transaction] = []):
    txs = []
    total = 0
    while True:
        tx = noise_simulation.post_fake_tx(send_tos=False)
        if total + tx.size_in_kb > config.PREFERRED_MAX_BLOCK_SIZE_KB:
            break
        total += tx.size_in_kb
        txs.append(tx.to_dict())
    return txs + transactions

def create_block_for_commit_tx(leader, followers, tx_com, prev_block):
    print('Start from block:', prev_block['_id'])
    # Create block for commit transaction
    blk1 = ordering_service.begin_consensus(
        pending_txs=rand_block_data() + [tx_com],
        leader=leader, 
        followers=followers,
        prev_block=prev_block,
        save=False
    ).to_dict()
    print("Block for commit TX: ", blk1['_id'])
    return blk1

def create_block_for_open_tx(leader, followers, tx_open, prev_block, t_open):
    com_window = t_open - 1
    blocks = []
    # Create blocks before the open tx
    for i in range(com_window):
        prev_block = ordering_service.begin_consensus(
            pending_txs=rand_block_data(), 
            leader=leader, 
            followers=followers,
            prev_block=prev_block,
            save=False
        ).to_dict()
        blocks.append(prev_block)
        print(f"\rOpen window: Created block {i+1}/{com_window}", end='')
    
    # Create block for the open tx
    prev_block = ordering_service.begin_consensus(
        pending_txs=rand_block_data() + [tx_open], 
        leader=leader, 
        followers=followers,
        prev_block=prev_block,
        save=False
    ).to_dict()
    blocks.append(prev_block)
    
    print("\nBlock for open TX: ", prev_block['_id'])
    
    return blocks, prev_block

def create_blocks_for_challenge_window(leader, followers, prev_block, t_chal):
    # Create blocks for the challenge time
    blocks = []
    for i in range(t_chal):
        prev_block = ordering_service.begin_consensus(
            pending_txs=BLK_SEEDS[i], 
            leader=leader, 
            followers=followers,
            prev_block=prev_block,
            save=False
        ).to_dict()
        blocks.append(prev_block)
        print(f"\rChallenge window: Created block {i+1}/{t_chal}", end='')
    return blocks, prev_block

def simulate(tx_com: dict, tx_open: dict, t_open: int, t_chal: int, t_wait: int, cache: bool = True) -> list[dict]:
    global START_BLK_ID
    
    if not isinstance(tx_com, dict) or not isinstance(tx_open, dict):
        raise Exception('tx_com and tx_open must be dictionaries.')
    
    if cache and ledger.find_transaction_by_id(tx_open['_id']):
        return
    
    print("Simulating blockchain for challenge window")
    prev_block = database.get_latest_block()
    START_BLK_ID = prev_block['_id']
    blocks = []
    leader, followers = ordering_service.get_orderers()
    
    prev_block = create_block_for_commit_tx(
        leader=leader, 
        followers=followers, 
        tx_com=tx_com, 
        prev_block=prev_block
    )
    blocks.append(prev_block)
    
    blks, prev_block = create_block_for_open_tx(
        leader=leader,
        followers=followers,
        tx_open=tx_open,
        prev_block=prev_block,
        t_open=t_open
    )
    
    blocks = blocks + blks
    
    # Skip wait window, simulate time by updating block number
    prev_block = {
        '_id': prev_block['_id'],
        'header': {
            'number': prev_block['header']['number'] + t_wait,
            'data_hash': prev_block['header']['data_hash'],
        }
    }
    print("")
    
    blks, prev_block = create_blocks_for_challenge_window(
        leader=leader,
        followers=followers,
        prev_block=prev_block,
        t_chal=t_chal
    )
    
    blocks = blocks + blks
    
    print("\nSaving blocks to database")
    database.insert("ledgers", blocks)
    
def clean():
    global START_BLK_ID
    print('cleaning database after block: ', START_BLK_ID)
    if START_BLK_ID > -1:
        database.delete_blocks_after(START_BLK_ID)
        START_BLK_ID = -1

